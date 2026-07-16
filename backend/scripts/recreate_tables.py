"""
若茗 PaaS - 数据库结构初始化
每次启动时删除并重建所有表
"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy import text  # noqa: E402


async def recreate_tables():
    from app.database import _write_engine, Base

    from app.modules.user.models import SysUser, SysApiKey
    from app.modules.permission.models import (
        SysRole, SysPermission, SysColumnPermission,
        SysUserRole, SysRolePermission, SysUserPermission, SysRoleDept
    )
    from app.modules.system.models import SysDept, SysDictType, SysDictItem
    from app.modules.tenant.models import SysTenant, SysTenantUsage
    from app.modules.audit.models import SysAuditLog, SysLoginLog, SysSecurityEvent
    from app.modules.config_center.models import SysConfig
    from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog
    from app.modules.message.models import SysNotice, SysUserMessage
    from app.modules.file_center.models import SysFile
    from app.modules.integration.models import SysIntegrationConnection, SysExternalIdentity, SysContactSyncLog

    from app.ai.conversation.models import (
        AiConversation, AiMessage, AiEntityMemory, AiKeyValueMemory, AiCallLog
    )
    from app.ai.llm.models import AiModelConfig
    from app.ai.agent.models import (
        AiAgent, AiSceneConfig, AiWorkflow, AiWorkflowVersion,
        AiWorkflowRun, AiWorkflowNodeRun
    )
    from app.ai.prompt.models import AiPromptTemplate, AiPromptVersion
    from app.ai.tool.models import AiTool
    from app.ai.knowledge.models import (
        AiKnowledgeBase, AiKnowledgeBaseShare, AiKnowledgeDoc,
        AiKnowledgeChunk, AiKnowledgeUploadPart, AiKnowledgeTask
    )

    async with _write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # sys_config_history 没有 ORM 模型，用原生 SQL 建表
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
            "CREATE INDEX IF NOT EXISTS ix_sys_config_history_config_key ON sys_config_history (config_key)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sys_config_history_changed_at ON sys_config_history (changed_at)"
        ))
    print("Tables recreated successfully")

    # 初始化内置计划任务种子数据
    await seed_scheduled_tasks()
    print("Seed data initialized")


async def seed_scheduled_tasks():
    """初始化内置计划任务种子数据"""
    from app.database import AsyncSessionFactory
    from app.modules.monitor.models import SysScheduledTask

    seed_tasks = [
        {
            "name": "知识库文档向量化",
            "task_type": "interval",
            "func_name": "app.ai.knowledge.tasks.index_document",
            "interval_seconds": 300,
            "is_once": False,
            "status": 0,  # 默认停用，按需启用
            "remark": "对待索引文档进行向量化入库处理（自动限速 10次/分）",
        },
        {
            "name": "知识库全量重建索引",
            "task_type": "cron",
            "func_name": "app.ai.knowledge.tasks.reindex_all_task",
            "cron_expr": "0 3 * * 0",  # 每周日凌晨3点
            "is_once": False,
            "status": 0,
            "remark": "全量重建所有知识库向量索引，建议低峰期执行",
        },
        {
            "name": "知识库单文档重建索引",
            "task_type": "interval",
            "func_name": "app.ai.knowledge.tasks.reindex_single_task",
            "interval_seconds": 600,
            "is_once": False,
            "status": 0,
            "remark": "对标记为需要重建的单文档进行索引更新",
        },
        {
            "name": "删除文档向量数据",
            "task_type": "interval",
            "func_name": "app.ai.knowledge.tasks.delete_document_vectors",
            "interval_seconds": 3600,
            "is_once": False,
            "status": 0,
            "remark": "清理已删除文档的向量数据（垃圾回收）",
        },
        {
            "name": "抓取 URL 内容并索引",
            "task_type": "interval",
            "func_name": "app.ai.knowledge.tasks.fetch_url_task",
            "interval_seconds": 86400,  # 每天
            "is_once": False,
            "status": 0,
            "remark": "定时抓取配置的 URL 页面内容并写入知识库",
        },
        {
            "name": "调用 API 获取内容并索引",
            "task_type": "interval",
            "func_name": "app.ai.knowledge.tasks.fetch_api_task",
            "interval_seconds": 86400,
            "is_once": False,
            "status": 0,
            "remark": "定时调用外部 API 获取数据并写入知识库",
        },
    ]

    async with AsyncSessionFactory() as db:
        for item in seed_tasks:
            task = SysScheduledTask(**item)
            db.add(task)
        await db.commit()
    print(f"  - 写入 {len(seed_tasks)} 条内置计划任务")


if __name__ == "__main__":
    asyncio.run(recreate_tables())
