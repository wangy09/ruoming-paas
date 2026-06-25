"""
若茗 PaaS - 数据库结构初始化
每次启动时删除并重建所有表
"""
import asyncio
import sys

sys.path.insert(0, '/app')


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
    print("Tables recreated successfully")


if __name__ == "__main__":
    asyncio.run(recreate_tables())