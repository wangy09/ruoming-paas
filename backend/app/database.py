"""
若茗 PaaS - 数据库连接与 Session 管理
Author: ruoming
"""
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = structlog.get_logger(__name__)

# ── 异步引擎 ──────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,          # 每次取连接前 ping，自动剔除失效连接
    echo=settings.DEBUG,         # 开发环境打印 SQL
)

# ── Session 工厂 ──────────────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,      # 提交后对象仍可访问属性，避免额外查询
    autocommit=False,
    autoflush=False,
)


# ── 声明基类 ──────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类"""
    pass


# ── 依赖注入 DB Session ───────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖函数，提供异步 DB Session。
    自动提交/回滚，完成后关闭连接。
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── 数据库初始化（启动时调用）────────────────────────────────────────────────
async def init_db() -> None:
    """创建所有表（开发/测试环境使用，生产用 Alembic）"""
    async with engine.begin() as conn:
        # 确保 pgvector 扩展已安装
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_initialized")


async def close_db() -> None:
    """关闭数据库连接池（应用关闭时调用）"""
    await engine.dispose()
    logger.info("database_connection_closed")
