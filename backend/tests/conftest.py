"""
若茗 PaaS - 测试配置与 Fixtures
Author: ruoming
"""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

# 测试数据库 URL（独立测试库，不影响开发库）
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/ruoming_dev", "/ruoming_test"
)

# 测试引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """创建测试数据库表结构"""
    async with test_engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """提供测试 DB Session（每个测试后回滚，保证隔离）"""
    async with test_engine.begin() as conn:
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """提供测试 HTTP 客户端"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"
