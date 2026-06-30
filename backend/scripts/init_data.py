"""
若茗 PaaS - 初始化种子数据
首次启动后执行，创建：超管账号、默认租户、基础权限数据
Author: ruoming
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def init_data(reset: bool = False) -> None:
    from app.config import settings
    from app.core.logging import setup_logging
    from app.core.security import hash_password
    from app.database import AsyncSessionFactory
    from app.modules.permission.models import (
        SysPermission, SysRole, SysRolePermission, SysUserRole,
    )
    from app.modules.message.models import SysNotice, SysUserMessage
    from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog
    from app.modules.tenant.models import SysTenant
    from app.modules.user.models import SysUser
    from sqlalchemy import select, delete

    setup_logging()

    import structlog
    logger = structlog.get_logger(__name__)

    async with AsyncSessionFactory() as db:
        # ── 1. 检查是否已初始化 ────────────────────────────────────────
        existing = await db.execute(
            select(SysUser).where(SysUser.is_superplatform == True)  # noqa: E712
        )
        if existing.scalar_one_or_none() and not reset:
            logger.info("already_initialized", msg="种子数据已存在，跳过初始化")
            return

        if reset:
            logger.info("reset_mode", msg="进入重置模式，清理现有数据")
            await db.execute(delete(SysTaskExecutionLog))
            await db.execute(delete(SysScheduledTask))
            await db.execute(delete(SysUserMessage))
            await db.execute(delete(SysNotice))
            await db.execute(delete(SysUserRole))
            await db.execute(delete(SysRolePermission))
            await db.execute(delete(SysPermission))
            await db.execute(delete(SysRole))
            await db.execute(delete(SysTenant))
            await db.execute(delete(SysUser))
            await db.flush()
            logger.info("data_cleared", msg="现有数据已清理")

        # ── 2. 创建平台超管 ───────────────────────────────────────────
        admin = SysUser(
            username="admin",
            password=hash_password("ruoming@2024"),
            nickname="平台超管",
            email="admin@ruoming.io",
            is_superplatform=True,
            status=1,
            tenant_id=None,
        )
        db.add(admin)
        await db.flush()
        logger.info("superadmin_created", user_id=admin.id)

        # ── 3. 创建默认租户 ───────────────────────────────────────────
        default_tenant = SysTenant(
            name="默认租户",
            code="default",
            plan="enterprise",
            max_users=1000,
            max_storage_gb=100,
            max_api_calls_day=100000,
            max_ai_tokens_day=10000000,
            max_concurrent=50,
            status=1,
            contact_email="admin@ruoming.io",
            registered_by=admin.id,
            approved_by=admin.id,
        )
        db.add(default_tenant)
        await db.flush()
        logger.info("default_tenant_created", tenant_id=default_tenant.id)

        # ── 4. 创建租户管理员角色 ─────────────────────────────────────
        tenant_admin_role = SysRole(
            name="租户管理员",
            code="tenant:admin",
            description="租户内最高权限角色",
            parent_id=0,
            data_scope=1,
            status=1,
            sort=1,
            tenant_id=None,
            is_system=True,
        )
        db.add(tenant_admin_role)

        normal_role = SysRole(
            name="普通用户",
            code="tenant:user",
            description="普通成员，基本查看权限",
            parent_id=0,
            data_scope=5,
            status=1,
            sort=10,
            tenant_id=None,
            is_system=True,
        )
        db.add(normal_role)
        await db.flush()

        # ── 5. 创建基础权限数据 ───────────────────────────────────────
        permissions_data = _get_default_permissions()
        perm_objects = []
        code_to_id = {}

        for p in permissions_data:
            # 过滤掉 parent_code 和 is_system（用于建立关系，不写入数据库）
            perm_data = {k: v for k, v in p.items() if k not in ("parent_code", "is_system")}
            perm = SysPermission(**perm_data)
            db.add(perm)
            perm_objects.append(perm)
        await db.flush()

        # 建立父级关系（通过 code 映射）
        for p, perm in zip(permissions_data, perm_objects):
            code_to_id[p["code"]] = perm.id
            if p.get("parent_code"):
                parent_id = code_to_id.get(p["parent_code"])
                if parent_id:
                    perm.parent_id = parent_id
        await db.flush()

        # 给租户管理员角色分配所有权限
        for perm in perm_objects:
            db.add(SysRolePermission(
                role_id=tenant_admin_role.id,
                permission_id=perm.id,
            ))
        await db.flush()

        # ── 6. 初始化字典数据 ──────────────────────────────────────────
        await init_dicts(db)
        await db.flush()

        # ── 7. 初始化测试计划任务 ─────────────────────────────────────
        db.add(SysScheduledTask(
            name="rmtask_test",
            task_type="interval",
            func_name="rmtask_test",
            interval_seconds=60,
            is_once=False,
            status=1,
            remark="计划任务测试用例",
        ))
        await db.flush()

        await db.commit()
        logger.info(
            "seed_data_initialized",
            admin_id=admin.id,
            tenant_id=default_tenant.id,
            permissions=len(perm_objects),
        )

        print("\n" + "="*60)
        print("✅ 若茗 PaaS 初始化完成！")
        print(f"   超管账号: admin")
        print(f"   超管密码: ruoming@2024")
        print(f"   API 文档: http://localhost:8000/api/docs")
        print("="*60 + "\n")


def _get_default_permissions() -> list[dict]:
    """默认权限数据"""
    perms = [
        # ── 系统管理（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "系统管理", "code": "system",
            "perm_type": "menu", "path": "/system", "component": "",
            "icon": "Setting", "sort": 100, "is_visible": True,
        },
        # 部门管理菜单
        {
            "parent_id": 0, "parent_code": "system", "name": "部门管理", "code": "system:dept:menu",
            "perm_type": "menu", "path": "/system/depts",
            "component": "system/dept/index", "icon": "Grid", "sort": 105, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "查询部门", "code": "system:dept:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "新增部门", "code": "system:dept:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "编辑部门", "code": "system:dept:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "删除部门", "code": "system:dept:delete", "perm_type": "button", "sort": 4},
        # 用户管理菜单
        {
            "parent_id": 0, "parent_code": "system", "name": "用户管理", "code": "system:user:menu",
            "perm_type": "menu", "path": "/system/users",
            "component": "system/user/index", "icon": "User", "sort": 110, "is_visible": True,
        },
        # 用户按钮权限
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "查询用户", "code": "system:user:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "新增用户", "code": "system:user:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "编辑用户", "code": "system:user:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "删除用户", "code": "system:user:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "重置密码", "code": "system:user:reset_pwd", "perm_type": "button", "sort": 5},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "分配角色", "code": "system:user:assign_role", "perm_type": "button", "sort": 6},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "导出用户", "code": "system:user:export", "perm_type": "button", "sort": 7},
        # ── 用户列权限示例 ────────────────────────────────────────────────
        {"parent_id": 0,  "parent_code": "system:user:menu","name": "用户手机号列", "code": "system:user:column:phone",
         "perm_type": "column", "resource": "user_list", "sort": 1},
        {"parent_id": 0,  "parent_code": "system:user:menu","name": "用户邮箱列", "code": "system:user:column:email",
         "perm_type": "column", "resource": "user_list", "sort": 2},
        # 角色管理菜单
        {
            "parent_id": 0, "parent_code": "system", "name": "角色管理", "code": "system:role:menu",
            "perm_type": "menu", "path": "/system/roles",
            "component": "system/role/index", "icon": "UserFilled", "sort": 120, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "查询角色", "code": "system:role:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "新增角色", "code": "system:role:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "编辑角色", "code": "system:role:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "删除角色", "code": "system:role:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "分配权限", "code": "system:role:assign_perm", "perm_type": "button", "sort": 5},
        # 角色授权菜单（独立页面）
        {
            "parent_id": 0, "parent_code": "system", "name": "角色授权", "code": "system:role_permission:menu",
            "perm_type": "menu", "path": "/system/role-permission",
            "component": "system/role-permission/index", "icon": "Key", "sort": 125, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:role_permission:menu", "name": "查看授权", "code": "system:role_permission:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:role_permission:menu", "name": "保存授权", "code": "system:role_permission:save", "perm_type": "button", "sort": 2},
        # 菜单管理（权限管理页面）
        {
            "parent_id": 0, "parent_code": "system", "name": "菜单管理", "code": "system:permission:menu",
            "perm_type": "menu", "path": "/system/permissions",
            "component": "system/permission/index", "icon": "Lock", "sort": 130, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "查询菜单", "code": "system:permission:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "新增菜单", "code": "system:permission:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "编辑菜单", "code": "system:permission:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "删除菜单", "code": "system:permission:delete", "perm_type": "button", "sort": 4},
        # ── 字典管理（子菜单）────────────────────────────────────────
        {
            "parent_id": 0, "parent_code": "system", "name": "字典管理", "code": "system:dict:menu",
            "perm_type": "menu", "path": "/system/dicts",
            "component": "system/dict/index", "icon": "Reading", "sort": 140, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "查询字典", "code": "system:dict:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "新增字典", "code": "system:dict:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "编辑字典", "code": "system:dict:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "删除字典", "code": "system:dict:delete", "perm_type": "button", "sort": 4},
        # ── 审计日志（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "审计日志", "code": "audit",
            "perm_type": "menu", "path": "/audit", "component": "",
            "icon": "Notebook", "sort": 300, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "audit", "name": "操作日志", "code": "audit:log:menu",
            "perm_type": "menu", "path": "/audit/logs",
            "component": "audit/logs/index", "icon": "List", "sort": 310, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "audit:log:menu", "name": "查询操作日志", "code": "audit:log:view", "perm_type": "button", "sort": 1},
        {
            "parent_id": 0, "parent_code": "audit", "name": "登录日志", "code": "audit:login:menu",
            "perm_type": "menu", "path": "/audit/login-logs",
            "component": "audit/login/index", "icon": "Key", "sort": 320, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "audit:login:menu", "name": "查询登录日志", "code": "audit:login:view", "perm_type": "button", "sort": 1},
        # ── 消息中心（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "消息中心", "code": "message",
            "perm_type": "menu", "path": "/message", "component": "",
            "icon": "Bell", "sort": 350, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "message", "name": "平台公告", "code": "message:notice:menu",
            "perm_type": "menu", "path": "/message/notices",
            "component": "message/notice/index", "icon": "Notification", "sort": 360, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "message:notice:menu", "name": "查询公告", "code": "message:notice:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "message:notice:menu", "name": "新增公告", "code": "message:notice:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "message:notice:menu", "name": "编辑公告", "code": "message:notice:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "message:notice:menu", "name": "删除公告", "code": "message:notice:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "message:notice:menu", "name": "发布公告", "code": "message:notice:publish", "perm_type": "button", "sort": 5},
        {
            "parent_id": 0, "parent_code": "message", "name": "我的消息", "code": "message:inbox:menu",
            "perm_type": "menu", "path": "/message/inbox",
            "component": "message/inbox/index", "icon": "Message", "sort": 370, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "message:inbox:menu", "name": "查看消息", "code": "message:inbox:view", "perm_type": "button", "sort": 1},
        # ── 开发工具（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "开发工具", "code": "dev",
            "perm_type": "menu", "path": "/dev", "component": "",
            "icon": "Tools", "sort": 380, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "dev", "name": "代码生成", "code": "dev:codegen:menu",
            "perm_type": "menu", "path": "/dev/codegen",
            "component": "dev/codegen/index", "icon": "DocumentAdd", "sort": 390, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "dev:codegen:menu", "name": "查看代码生成", "code": "dev:codegen:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "dev:codegen:menu", "name": "生成代码预览", "code": "dev:codegen:preview", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "dev:codegen:menu", "name": "写入生成文件", "code": "dev:codegen:write", "perm_type": "button", "sort": 3},
        # ── AI 管理（根菜单）─────────────────────────────────────────
        {
            "parent_id": 0, "name": "AI 管理", "code": "ai",
            "perm_type": "menu", "path": "/ai", "component": "",
            "icon": "MagicStick", "sort": 200, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "ai", "name": "AI 对话", "code": "ai:chat:menu",
            "perm_type": "menu", "path": "/ai/chat",
            "component": "ai/chat/index", "icon": "ChatDotRound", "sort": 205, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:chat:menu", "name": "发起对话", "code": "ai:chat:send", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:chat:menu", "name": "删除对话", "code": "ai:chat:delete", "perm_type": "button", "sort": 2},
        {
            "parent_id": 0, "parent_code": "ai", "name": "模型管理", "code": "ai:model:menu",
            "perm_type": "menu", "path": "/ai/models",
            "component": "ai/model/index", "icon": "Cpu", "sort": 210, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:model:menu", "name": "接入模型", "code": "ai:model:create", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:model:menu", "name": "编辑模型", "code": "ai:model:update", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "ai:model:menu", "name": "删除模型", "code": "ai:model:delete", "perm_type": "button", "sort": 3},
        {
            "parent_id": 0, "parent_code": "ai", "name": "Agent 管理", "code": "ai:agent:menu",
            "perm_type": "menu", "path": "/ai/agents",
            "component": "ai/agent/index", "icon": "Grid", "sort": 220, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:agent:menu", "name": "新建 Agent", "code": "ai:agent:create", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:agent:menu", "name": "编辑 Agent", "code": "ai:agent:update", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "ai:agent:menu", "name": "删除 Agent", "code": "ai:agent:delete", "perm_type": "button", "sort": 3},
        {
            "parent_id": 0, "parent_code": "ai", "name": "知识库", "code": "ai:knowledge:menu",
            "perm_type": "menu", "path": "/ai/knowledge",
            "component": "ai/knowledge/index", "icon": "Reading", "sort": 230, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:knowledge:menu", "name": "新建知识库", "code": "ai:kb:create", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:knowledge:menu", "name": "编辑知识库", "code": "ai:kb:update", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "ai:knowledge:menu", "name": "删除知识库", "code": "ai:kb:delete", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "ai:knowledge:menu", "name": "上传文档", "code": "ai:kb:upload", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "ai:knowledge:menu", "name": "删除文档", "code": "ai:kb:doc:delete", "perm_type": "button", "sort": 5},
        {
            "parent_id": 0, "parent_code": "ai", "name": "对话历史", "code": "ai:conversation:menu",
            "perm_type": "menu", "path": "/ai/conversations",
            "component": "ai/conversation/index", "icon": "ChatDotRound", "sort": 240, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "ai", "name": "Prompt 模板", "code": "ai:prompt:menu",
            "perm_type": "menu", "path": "/ai/prompts",
            "component": "ai/prompt/index", "icon": "Document", "sort": 250, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:prompt:menu", "name": "新建模板", "code": "ai:prompt:create", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:prompt:menu", "name": "发布模板", "code": "ai:prompt:publish", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "ai:prompt:menu", "name": "删除模板", "code": "ai:prompt:delete", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "ai:prompt:menu", "name": "版本管理", "code": "ai:prompt:version", "perm_type": "button", "sort": 4},
        {
            "parent_id": 0, "parent_code": "ai", "name": "工具管理", "code": "ai:tool:menu",
            "perm_type": "menu", "path": "/ai/tools",
            "component": "ai/tool/index", "icon": "Tools", "sort": 260, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "ai:tool:menu", "name": "查看工具", "code": "ai:tool:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "ai:tool:menu", "name": "新建工具", "code": "ai:tool:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "ai:tool:menu", "name": "编辑工具", "code": "ai:tool:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "ai:tool:menu", "name": "删除工具", "code": "ai:tool:delete", "perm_type": "button", "sort": 4},

        # ── 系统监控（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "系统监控", "code": "monitor",
            "perm_type": "menu", "path": "/monitor", "component": "",
            "icon": "Monitor", "sort": 400, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "monitor", "name": "服务监控", "code": "monitor:server:menu",
            "perm_type": "menu", "path": "/monitor/server",
            "component": "monitor/server/index", "icon": "DataBoard", "sort": 410, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "monitor:server:menu", "name": "查看服务监控", "code": "monitor:server:view", "perm_type": "button", "sort": 1},
        {
            "parent_id": 0, "parent_code": "monitor", "name": "计划任务", "code": "monitor:task:menu",
            "perm_type": "menu", "path": "/monitor/task",
            "component": "monitor/task/index", "icon": "AlarmClock", "sort": 420, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "查询任务", "code": "monitor:task:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "新增任务", "code": "monitor:task:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "编辑任务", "code": "monitor:task:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "删除任务", "code": "monitor:task:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "立即执行", "code": "monitor:task:run", "perm_type": "button", "sort": 5},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "查看执行日志", "code": "monitor:task:log:view", "perm_type": "button", "sort": 6},
        {"parent_id": 0, "parent_code": "monitor:task:menu", "name": "清空日志", "code": "monitor:task:log:clear", "perm_type": "button", "sort": 7},

    ]

    for p in perms:
        p["is_system"] = True

    return perms


async def init_dicts(db) -> None:
    """初始化字典数据"""
    from sqlalchemy import select
    from app.modules.system.models import SysDictType, SysDictItem

    # 字典类型
    dict_types = [
        {"code": "system_user_status", "name": "用户状态", "sort": 1},
        {"code": "system_common_status", "name": "通用状态", "sort": 2},
        {"code": "system_data_scope", "name": "数据权限范围", "sort": 3},
        {"code": "system_tenant_status", "name": "租户状态", "sort": 4},
        {"code": "ai_agent_status", "name": "Agent状态", "sort": 5},
    ]

    for dt_data in dict_types:
        exists = await db.execute(
            select(SysDictType).where(SysDictType.code == dt_data["code"])
        )
        if exists.scalar_one_or_none():
            continue

        dt = SysDictType(
            name=dt_data["name"],
            code=dt_data["code"],
            sort=dt_data["sort"],
            status=1,
            is_system=True,
        )
        db.add(dt)
        await db.flush()

        # 字典项
        items = []
        if dt_data["code"] == "system_user_status":
            items = [
                {"label": "启用", "value": "true", "sort": 1, "is_default": True},
                {"label": "禁用", "value": "false", "sort": 2},
            ]
        elif dt_data["code"] == "system_common_status":
            items = [
                {"label": "正常", "value": "1", "sort": 1, "is_default": True},
                {"label": "停用", "value": "0", "sort": 2},
            ]
        elif dt_data["code"] == "system_data_scope":
            items = [
                {"label": "全部数据", "value": "1", "sort": 1, "is_default": True},
                {"label": "本部门", "value": "3", "sort": 2},
                {"label": "本部门及子部门", "value": "2", "sort": 3},
                {"label": "仅本人", "value": "4", "sort": 4},
                {"label": "自定义部门", "value": "5", "sort": 5},
            ]
        elif dt_data["code"] == "system_tenant_status":
            items = [
                {"label": "正常", "value": "active", "sort": 1, "is_default": True},
                {"label": "禁用", "value": "inactive", "sort": 2},
                {"label": "暂停", "value": "suspended", "sort": 3},
            ]
        elif dt_data["code"] == "ai_agent_status":
            items = [
                {"label": "草稿", "value": "draft", "sort": 1, "is_default": True},
                {"label": "启用", "value": "active", "sort": 2},
                {"label": "归档", "value": "archived", "sort": 3},
            ]

        for item_data in items:
            di = SysDictItem(
                type_id=dt.id,
                label=item_data["label"],
                value=item_data["value"],
                sort=item_data["sort"],
                status=1,
                is_default=item_data.get("is_default", False),
            )
            db.add(di)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(init_data(reset))
