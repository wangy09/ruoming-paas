"""
若茗 PaaS - 数据库连接与 Session 管理

读写分离支持：
  - 开发/测试环境：读写均使用同一主库（DATABASE_URL）
  - 生产环境：通过 DATABASE_REPLICA_URL 指定只读副本，
    get_write_session() → 主库，get_read_session() → 只读副本
  - 业务代码无感知：修改 Repository 基类的 db 参数即可，无需改任何 Service

Author: ruoming
"""
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = structlog.get_logger(__name__)

# ── 写库引擎（主库，始终使用）─────────────────────────────────────────────────
_write_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,      # 每次取连接前 ping，自动剔除失效连接
    echo=settings.DEBUG,     # 开发环境打印 SQL
)

# ── 只读副本引擎（生产环境可配置 DATABASE_REPLICA_URL 切换到只读副本）──────────
# 若未配置副本 URL，则与主库共用同一引擎（向后兼容，零改动）
_replica_url = getattr(settings, "DATABASE_REPLICA_URL", "") or None
_read_engine = (
    create_async_engine(
        _replica_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )
    if _replica_url
    else _write_engine  # 未配置副本时回退到主库，保持向后兼容
)

if _replica_url:
    logger.info("read_write_splitting_enabled", replica_url=_replica_url[:30] + "...")
else:
    logger.debug("read_write_splitting_disabled", note="DATABASE_REPLICA_URL 未配置，读写同库")

# ── Session 工厂 ──────────────────────────────────────────────────────────────
# 写操作 Session（INSERT / UPDATE / DELETE）
_WriteSessionFactory = async_sessionmaker(
    _write_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 读操作 Session（SELECT）
_ReadSessionFactory = async_sessionmaker(
    _read_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 兼容旧代码的默认 Session 工厂（指向写库）
AsyncSessionFactory = _WriteSessionFactory


# ── 声明基类 ──────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类"""
    pass


def _import_models_for_metadata() -> None:
    """Import ORM models so Base.metadata contains all tables before create_all."""
    from app.modules.user.models import SysUser, SysApiKey  # noqa: F401
    from app.modules.permission.models import (  # noqa: F401
        SysRole, SysPermission, SysColumnPermission,
        SysUserRole, SysRolePermission, SysUserPermission, SysRoleDept,
    )
    from app.modules.system.models import SysDept, SysDictType, SysDictItem  # noqa: F401
    from app.modules.tenant.models import SysTenant, SysTenantUsage  # noqa: F401
    from app.modules.audit.models import SysAuditLog, SysLoginLog, SysSecurityEvent  # noqa: F401
    from app.modules.config_center.models import SysConfig  # noqa: F401
    from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog  # noqa: F401
    from app.modules.message.models import SysNotice, SysUserMessage  # noqa: F401
    from app.modules.file_center.models import SysFile  # noqa: F401
    from app.modules.integration.models import (  # noqa: F401
        SysIntegrationConnection, SysExternalIdentity, SysContactSyncLog,
    )

    from app.ai.conversation.models import (  # noqa: F401
        AiConversation, AiMessage, AiEntityMemory, AiKeyValueMemory, AiCallLog,
    )
    from app.ai.llm.models import AiModelConfig  # noqa: F401
    from app.ai.agent.models import (  # noqa: F401
        AiAgent, AiSceneConfig, AiWorkflow, AiWorkflowVersion,
        AiWorkflowRun, AiWorkflowNodeRun,
    )
    from app.ai.prompt.models import AiPromptTemplate, AiPromptVersion  # noqa: F401
    from app.ai.tool.models import AiTool  # noqa: F401
    from app.ai.knowledge.models import (  # noqa: F401
        AiKnowledgeBase, AiKnowledgeBaseShare, AiKnowledgeDoc,
        AiKnowledgeChunk, AiKnowledgeUploadPart, AiKnowledgeTask,
    )
    from app.modules.codegen.models import GenTable, GenTableColumn  # noqa: F401


# ── 依赖注入：写 Session（INSERT / UPDATE / DELETE） ────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖函数，提供写库异步 DB Session（向后兼容接口）。
    自动提交/回滚，完成后关闭连接。
    """
    async with _WriteSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    """
    写库 Session（显式使用）。
    INSERT / UPDATE / DELETE 操作应使用此依赖。
    """
    async with _WriteSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """
    只读副本 Session。
    纯查询接口（列表页、统计看板等）可使用此依赖，降低主库压力。
    未配置 DATABASE_REPLICA_URL 时自动回退到主库（无需修改代码）。
    """
    async with _ReadSessionFactory() as session:
        try:
            yield session
        except Exception:
            raise
        finally:
            await session.close()


# ── 数据库初始化（启动时调用）────────────────────────────────────────────────
async def init_db() -> None:
    """创建所有表（开发/测试环境使用，生产用 Alembic）"""
    _import_models_for_metadata()

    async with _write_engine.begin() as conn:
        # 确保 pgvector 扩展已安装
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sys_config_history (
                id          BIGSERIAL PRIMARY KEY,
                config_key  VARCHAR(256) NOT NULL,
                scope_type  VARCHAR(20) NOT NULL,
                scope_id    BIGINT,
                old_value   TEXT,
                new_value   TEXT,
                changed_by  BIGINT,
                changed_at  TIMESTAMPTZ DEFAULT NOW(),
                remark      TEXT
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sys_config_history_config_key "
            "ON sys_config_history (config_key)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sys_config_history_changed_at "
            "ON sys_config_history (changed_at)"
        ))
    logger.info("database_initialized")


async def close_db() -> None:
    """关闭数据库连接池（应用关闭时调用）"""
    await _write_engine.dispose()
    if _replica_url:
        await _read_engine.dispose()
    logger.info("database_connection_closed")


# ── 兼容旧代码：engine 指向写库 ───────────────────────────────────────────────
engine = _write_engine
