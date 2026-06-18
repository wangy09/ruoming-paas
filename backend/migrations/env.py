"""
若茗 PaaS - Alembic 迁移环境配置
Author: ruoming
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 添加项目根目录到 PATH，使 app 包可以被导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Base

# ── 导入所有模型（Alembic autogenerate 需要）────────────────────────────────
# 按需添加新模块的模型，确保 autogenerate 能感知所有表变更
from app.modules.user.models import SysUser, SysApiKey  # noqa: F401
from app.modules.tenant.models import SysTenant, SysTenantUsage  # noqa: F401
from app.modules.permission.models import (  # noqa: F401
    SysRole, SysPermission, SysColumnPermission,
    SysUserRole, SysRolePermission, SysUserPermission, SysRoleDept,
)
from app.modules.organization.models import SysDept  # noqa: F401
from app.modules.audit.models import SysAuditLog, SysLoginLog, SysSecurityEvent  # noqa: F401
from app.modules.config_center.models import SysConfig  # noqa: F401

# M4 AI 模型（Alembic autogenerate 需要导入所有 ORM 模型）
from app.ai.llm.models import AiModelConfig  # noqa: F401
from app.ai.conversation.models import AiConversation, AiMessage, AiCallLog  # noqa: F401
from app.ai.agent.models import (  # noqa: F401
    AiAgent, AiSceneConfig,
    AiWorkflow, AiWorkflowVersion, AiWorkflowRun, AiWorkflowNodeRun,
)
from app.ai.knowledge.models import (  # noqa: F401
    AiKnowledgeBase, AiKnowledgeBaseShare, AiKnowledgeDoc, AiKnowledgeChunk,
)
from app.ai.prompt.models import AiPromptTemplate, AiPromptVersion  # noqa: F401
from app.ai.tool.models import AiTool  # noqa: F401

# Alembic Config 对象
config = context.config

# 解释日志配置文件
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 Metadata（autogenerate 使用）
target_metadata = Base.metadata

# 从 Pydantic Settings 读取数据库 URL（同步连接，用于迁移）
# 注意：迁移用同步驱动，运行时用 asyncpg
db_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """离线模式（不需要数据库连接，只生成 SQL 脚本）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式（连接数据库执行迁移）"""
    from sqlalchemy.engine import create_engine

    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
