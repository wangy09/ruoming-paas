"""
若茗 PaaS - 初始化种子数据
首次启动后执行，创建：超管账号、默认租户、基础权限数据
支持版本化增量更新，每次数据变更新增一个版本
Author: ruoming
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INIT_VERSIONS = [
    {"version": "1.0.0", "name": "v1.0.0 初始版本：超管、租户、基础权限、字典、配置", "func": None},
]


async def init_data(reset: bool = False) -> None:
    from app.config import settings
    from app.core.logging import setup_logging
    from app.core.security import hash_password
    from app.database import AsyncSessionFactory
    from app.modules.permission.models import (
        SysPermission, SysRole, SysRolePermission, SysUserRole,
    )
    from app.modules.config_center.models import SysConfig
    from app.modules.file_center.models import SysFile
    from app.modules.message.models import SysNotice, SysUserMessage
    from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog
    from app.modules.tenant.models import SysTenant
    from app.modules.user.models import SysUser
    from app.modules.system.models import SysInitVersion
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
            logger.info("already_initialized", msg="种子数据已初始化，跳过执行")
            return

        if reset:
            logger.info("reset_mode", msg="进入重置模式，清理现有数据")
            await db.execute(delete(SysTaskExecutionLog))
            await db.execute(delete(SysScheduledTask))
            await db.execute(delete(SysFile))
            await db.execute(delete(SysUserMessage))
            await db.execute(delete(SysNotice))
            await db.execute(delete(SysConfig))
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
            password=hash_password("ruoming@2026"),
            nickname="平台超管",
            email="sbxwlf@163.com",
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
            dashboard_template="tenant",
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
            dashboard_template="personal",
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

        # ── 7. 初始化运行时配置 ───────────────────────────────────────
        await init_runtime_configs(db, settings)
        await db.flush()

        # ── 8. 初始化内置计划任务 ─────────────────────────────────────
        _builtin_tasks = [
            {
                "name": "rmtask_test",
                "task_type": "interval",
                "func_name": "rmtask_test",
                "interval_seconds": 60,
                "is_once": False,
                "status": 1,
                "remark": "计划任务测试用例",
            },
            {
                "name": "知识库文档向量化",
                "task_type": "interval",
                "func_name": "app.ai.knowledge.tasks.index_document",
                "interval_seconds": 300,
                "is_once": False,
                "status": 0,
                "remark": "对待索引文档进行向量化入库处理（自动限速 10次/分）",
            },
            {
                "name": "知识库全量重建索引",
                "task_type": "cron",
                "func_name": "app.ai.knowledge.tasks.reindex_all_task",
                "cron_expr": "0 3 * * 0",
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
                "interval_seconds": 86400,
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
        for _task_data in _builtin_tasks:
            db.add(SysScheduledTask(**_task_data))
        await db.flush()
        await clear_permission_cache()

        for version_info in INIT_VERSIONS:
            db.add(SysInitVersion(
                version=version_info["version"],
                name=version_info["name"],
                executed_at=datetime.now().isoformat(timespec="seconds"),
            ))

        await db.commit()
        logger.info(
            "seed_data_initialized",
            admin_id=admin.id,
            tenant_id=default_tenant.id,
            permissions=len(perm_objects),
            versions=len(INIT_VERSIONS),
        )

        print("\n" + "="*60)
        print("✅ 若茗 PaaS 初始化完成！")
        print(f"   超管账号: admin")
        print(f"   超管密码: ruoming@2026")
        print(f"   API 文档: http://localhost:8000/api/docs")
        print("="*60 + "\n")


def _get_default_permissions() -> list[dict]:
    """默认权限数据"""
    perms = [
        # ── 工作台（固定首位）────────────────────────────────────────
        {
            "parent_id": 0, "name": "工作台", "code": "dashboard:menu",
            "perm_type": "menu", "path": "/dashboard",
            "component": "dashboard/index", "icon": "Odometer", "sort": 0,
            "is_visible": True, "is_cache": True,
        },
        # ── 基础管理分组（根菜单）────────────────────────────────────
        *_get_navigation_root_permissions(),
        # 部门管理菜单
        {
            "parent_id": 0, "parent_code": "org", "name": "部门管理", "code": "system:dept:menu",
            "perm_type": "menu", "path": "/system/depts",
            "component": "system/dept/index", "icon": "Grid", "sort": 20, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "查询部门", "code": "system:dept:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "新增部门", "code": "system:dept:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "编辑部门", "code": "system:dept:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:dept:menu", "name": "删除部门", "code": "system:dept:delete", "perm_type": "button", "sort": 4},
        # 用户管理菜单
        {
            "parent_id": 0, "parent_code": "org", "name": "用户管理", "code": "system:user:menu",
            "perm_type": "menu", "path": "/system/users",
            "component": "system/user/index", "icon": "User", "sort": 10, "is_visible": True,
        },
        # 用户按钮权限
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "查询用户", "code": "system:user:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "新增用户", "code": "system:user:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "编辑用户", "code": "system:user:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "删除用户", "code": "system:user:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "重置密码", "code": "system:user:reset_pwd", "perm_type": "button", "sort": 5},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "分配角色", "code": "system:user:assign_role", "perm_type": "button", "sort": 6},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "导出用户", "code": "system:user:export", "perm_type": "button", "sort": 7},
        {"parent_id": 0, "parent_code": "system:user:menu", "name": "同步用户", "code": "system:user:sync", "perm_type": "button", "sort": 8},
        # ── 用户列权限示例 ────────────────────────────────────────────────
        {"parent_id": 0,  "parent_code": "system:user:menu","name": "用户手机号列", "code": "system:user:column:phone",
         "perm_type": "column", "resource": "user_list", "sort": 1},
        {"parent_id": 0,  "parent_code": "system:user:menu","name": "用户邮箱列", "code": "system:user:column:email",
         "perm_type": "column", "resource": "user_list", "sort": 2},
        # 角色管理菜单
        {
            "parent_id": 0, "parent_code": "authz", "name": "角色管理", "code": "system:role:menu",
            "perm_type": "menu", "path": "/system/roles",
            "component": "system/role/index", "icon": "UserFilled", "sort": 20, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "查询角色", "code": "system:role:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "新增角色", "code": "system:role:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "编辑角色", "code": "system:role:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "删除角色", "code": "system:role:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "system:role:menu", "name": "分配权限", "code": "system:role:assign_perm", "perm_type": "button", "sort": 5},
        # 角色授权菜单（独立页面）
        {
            "parent_id": 0, "parent_code": "authz", "name": "角色授权", "code": "system:role_permission:menu",
            "perm_type": "menu", "path": "/system/role-permission",
            "component": "system/role-permission/index", "icon": "Key", "sort": 10, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:role_permission:menu", "name": "查看授权", "code": "system:role_permission:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:role_permission:menu", "name": "保存授权", "code": "system:role_permission:save", "perm_type": "button", "sort": 2},
        # 菜单管理（权限管理页面）
        {
            "parent_id": 0, "parent_code": "authz", "name": "菜单管理", "code": "system:permission:menu",
            "perm_type": "menu", "path": "/system/permissions",
            "component": "system/permission/index", "icon": "Lock", "sort": 30, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "查询菜单", "code": "system:permission:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "新增菜单", "code": "system:permission:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "编辑菜单", "code": "system:permission:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:permission:menu", "name": "删除菜单", "code": "system:permission:delete", "perm_type": "button", "sort": 4},
        # ── 字典管理（子菜单）────────────────────────────────────────
        {
            "parent_id": 0, "parent_code": "platform_config", "name": "字典管理", "code": "system:dict:menu",
            "perm_type": "menu", "path": "/system/dicts",
            "component": "system/dict/index", "icon": "Reading", "sort": 20, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "查询字典", "code": "system:dict:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "新增字典", "code": "system:dict:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "编辑字典", "code": "system:dict:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:dict:menu", "name": "删除字典", "code": "system:dict:delete", "perm_type": "button", "sort": 4},
        # 配置中心菜单
        {
            "parent_id": 0, "parent_code": "platform_config", "name": "配置中心", "code": "system:config:menu",
            "perm_type": "menu", "path": "/system/config",
            "component": "system/config/index", "icon": "Tools", "sort": 10, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:config:menu", "name": "查询配置", "code": "config:list", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:config:menu", "name": "新增配置", "code": "config:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:config:menu", "name": "编辑配置", "code": "config:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:config:menu", "name": "删除配置", "code": "config:delete", "perm_type": "button", "sort": 4},
        # 集成中心菜单
        {
            "parent_id": 0, "parent_code": "resource_integration", "name": "集成中心", "code": "system:integration:menu",
            "perm_type": "menu", "path": "/system/integrations",
            "component": "system/integration/index", "icon": "Connection", "sort": 20, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:integration:menu", "name": "查看集成", "code": "integration:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:integration:menu", "name": "管理集成", "code": "integration:manage", "perm_type": "button", "sort": 2},
        # 文件中心菜单
        {
            "parent_id": 0, "parent_code": "resource_integration", "name": "文件中心", "code": "system:file:menu",
            "perm_type": "menu", "path": "/system/files",
            "component": "system/file/index", "icon": "FolderOpened", "sort": 10, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "查询文件", "code": "system:file:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "上传文件", "code": "system:file:upload", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "编辑文件", "code": "system:file:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "下载文件", "code": "system:file:download", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "预览文件", "code": "system:file:preview", "perm_type": "button", "sort": 5},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "归档文件", "code": "system:file:archive", "perm_type": "button", "sort": 6},
        {"parent_id": 0, "parent_code": "system:file:menu", "name": "删除文件", "code": "system:file:delete", "perm_type": "button", "sort": 7},
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
        {"parent_id": 0, "parent_code": "audit:log:menu", "name": "清除日志", "code": "system:audit:clear", "perm_type": "button", "sort": 2},
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
        {"parent_id": 0, "parent_code": "dev:codegen:menu", "name": "删除代码生成", "code": "dev:codegen:delete", "perm_type": "button", "sort": 4},
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

        {
            "parent_id": 0, "parent_code": "monitor", "name": "熔断器监控", "code": "monitor:circuit:menu",
            "perm_type": "menu", "path": "/monitor/circuit",
            "component": "monitor/circuit/index", "icon": "Shield", "sort": 430, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "monitor:circuit:menu", "name": "查看熔断器", "code": "monitor:circuit:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "parent_code": "monitor:circuit:menu", "name": "重置熔断器", "code": "monitor:circuit:reset", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "parent_code": "monitor:circuit:menu", "name": "熔断", "code": "monitor:circuit:trip", "perm_type": "button", "sort": 3},

        # ── 帮助中心（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "帮助中心", "code": "help",
            "perm_type": "menu", "path": "/help", "component": "",
            "icon": "QuestionFilled", "sort": 450, "is_visible": True,
        },
        {
            "parent_id": 0, "parent_code": "help", "name": "用户手册", "code": "help:manual:menu",
            "perm_type": "menu", "path": "/help/manual",
            "component": "help/manual/index", "icon": "Reading", "sort": 451, "is_visible": True,
        },
        {"parent_id": 0, "parent_code": "help:manual:menu", "name": "查看用户手册", "code": "help:manual:view", "perm_type": "button", "sort": 1},

    ]

    for p in perms:
        p["is_system"] = True

    return perms


def _get_navigation_root_permissions() -> list[dict]:
    """拆分原系统管理，减少单个菜单下的子项数量。"""
    return [
        {
            "parent_id": 0,
            "name": "组织与账号",
            "code": "org",
            "perm_type": "menu",
            "path": "/org",
            "component": "",
            "icon": "OfficeBuilding",
            "sort": 100,
            "is_visible": True,
        },
        {
            "parent_id": 0,
            "name": "权限中心",
            "code": "authz",
            "perm_type": "menu",
            "path": "/authz",
            "component": "",
            "icon": "Lock",
            "sort": 110,
            "is_visible": True,
        },
        {
            "parent_id": 0,
            "name": "平台配置",
            "code": "platform_config",
            "perm_type": "menu",
            "path": "/platform-config",
            "component": "",
            "icon": "Setting",
            "sort": 120,
            "is_visible": True,
        },
        {
            "parent_id": 0,
            "name": "资源与集成",
            "code": "resource_integration",
            "perm_type": "menu",
            "path": "/resources",
            "component": "",
            "icon": "Connection",
            "sort": 130,
            "is_visible": True,
        },
    ]


async def clear_permission_cache() -> None:
    """清理用户权限缓存，确保菜单调整立即生效。"""
    try:
        from app.core.redis import get_redis_client

        redis = await get_redis_client()
        keys = [key async for key in redis.scan_iter("perm:user:*", count=100)]
        if keys:
            await redis.delete(*keys)
    except Exception:
        # Redis 不可用不应阻断初始化；缓存会在过期后自动刷新。
        return








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


async def init_runtime_configs(db, settings) -> None:
    """初始化可在配置中心维护的运行时配置。"""
    import json

    from app.modules.config_center.service import ConfigCenterService

    svc = ConfigCenterService(db)
    configs = [
        {
            "config_key": "site.title",
            "config_val": "若茗 PaaS",
            "val_type": "string",
            "category": "site",
            "config_type": "input",
            "label": "系统名称",
            "description": "浏览器标题、后台 Logo 文案、登录页标题",
            "is_public": True,
            "sort": 10,
        },
        {
            "config_key": "site.login_subtitle",
            "config_val": "企业级 AI 应用开发底座",
            "val_type": "string",
            "category": "site",
            "config_type": "input",
            "label": "登录页副标题",
            "is_public": True,
            "sort": 20,
        },
        {
            "config_key": "site.logo_url",
            "config_val": "/logo.svg",
            "val_type": "string",
            "category": "site",
            "config_type": "input",
            "label": "Logo 地址",
            "is_public": True,
            "sort": 30,
        },
        {
            "config_key": "ui.primary_color",
            "config_val": "#1677ff",
            "val_type": "string",
            "category": "ui",
            "config_type": "input",
            "label": "主题色",
            "regex": r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
            "is_public": True,
            "sort": 40,
        },
        {
            "config_key": "file.max_upload_size_mb",
            "config_val": str(settings.MAX_UPLOAD_SIZE_MB),
            "val_type": "int",
            "category": "file",
            "config_type": "number",
            "label": "最大上传大小（MB）",
            "min_value": 1,
            "max_value": 1024,
            "sort": 100,
        },
        {
            "config_key": "file.allowed_upload_extensions",
            "config_val": json.dumps(settings.ALLOWED_UPLOAD_EXTENSIONS, ensure_ascii=False),
            "val_type": "json",
            "category": "file",
            "config_type": "json",
            "label": "允许上传扩展名",
            "description": "JSON 数组，例如 [\"jpg\", \"png\", \"pdf\"]",
            "sort": 110,
        },
        {
            "config_key": "auth.login_fail_max_times",
            "config_val": str(settings.LOGIN_FAIL_MAX_TIMES),
            "val_type": "int",
            "category": "auth",
            "config_type": "number",
            "label": "登录失败最大次数",
            "min_value": 1,
            "max_value": 20,
            "sort": 200,
        },
        {
            "config_key": "auth.login_lock_minutes",
            "config_val": str(settings.LOGIN_LOCK_MINUTES),
            "val_type": "int",
            "category": "auth",
            "config_type": "number",
            "label": "登录锁定分钟数",
            "min_value": 1,
            "max_value": 1440,
            "sort": 210,
        },
        {
            "config_key": "ai.default_temperature",
            "config_val": str(settings.AI_DEFAULT_TEMPERATURE),
            "val_type": "number",
            "category": "ai",
            "config_type": "number",
            "label": "AI 默认温度",
            "min_value": 0,
            "max_value": 2,
            "sort": 300,
        },
        {
            "config_key": "ai.default_max_tokens",
            "config_val": str(settings.AI_DEFAULT_MAX_TOKENS),
            "val_type": "int",
            "category": "ai",
            "config_type": "number",
            "label": "AI 默认最大 Tokens",
            "min_value": 1,
            "max_value": 32768,
            "sort": 310,
        },
        {
            "config_key": "multi_tenant.enabled",
            "config_val": "true",
            "val_type": "bool",
            "category": "system",
            "config_type": "switch",
            "label": "多租户模式",
            "description": "开启后系统启用多租户隔离，关闭后所有用户共享同一数据空间",
            "is_public": False,
            "sort": 999,
        },
        {
            "config_key": "rate_limit.enabled",
            "config_val": "true",
            "val_type": "bool",
            "category": "rate_limit",
            "config_type": "switch",
            "label": "限流开关",
            "description": "开启后启用系统限流保护，关闭后所有限流规则失效",
            "is_public": False,
            "sort": 1,
        },
        {
            "config_key": "rate_limit.global.default",
            "config_val": "100/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "全局默认限流",
            "description": "所有接口的默认限流规则，格式：数字/单位（如 100/minute）",
            "is_public": False,
            "sort": 2,
        },
        {
            "config_key": "rate_limit.ip.default",
            "config_val": "300/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "IP 级限流",
            "description": "按 IP 地址的限流规则，防 DDoS 和爆破",
            "is_public": False,
            "sort": 3,
        },
        {
            "config_key": "rate_limit.user.default",
            "config_val": "60/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "用户级限流",
            "description": "按用户 ID 的限流规则，防单用户过度消耗",
            "is_public": False,
            "sort": 4,
        },
        {
            "config_key": "rate_limit.tenant.default",
            "config_val": "500/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "租户级限流",
            "description": "按租户 ID 的限流规则，防单租户拖垮系统",
            "is_public": False,
            "sort": 5,
        },
        {
            "config_key": "rate_limit.api.login",
            "config_val": "10/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "登录接口限流",
            "description": "登录接口的限流规则，更严格以防止暴力破解",
            "is_public": False,
            "sort": 6,
        },
        {
            "config_key": "rate_limit.api.register",
            "config_val": "5/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "注册接口限流",
            "description": "注册接口的限流规则",
            "is_public": False,
            "sort": 7,
        },
        {
            "config_key": "rate_limit.api.captcha",
            "config_val": "3/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "验证码接口限流",
            "description": "验证码发送接口的限流规则",
            "is_public": False,
            "sort": 8,
        },
        {
            "config_key": "rate_limit.ai.chat",
            "config_val": "30/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "AI 对话限流",
            "description": "AI 对话接口的限流规则",
            "is_public": False,
            "sort": 9,
        },
        {
            "config_key": "rate_limit.ai.agent",
            "config_val": "30/minute",
            "val_type": "string",
            "category": "rate_limit",
            "config_type": "input",
            "label": "AI Agent 限流",
            "description": "AI Agent 执行接口的限流规则",
            "is_public": False,
            "sort": 10,
        },
    ]

    for item in configs:
        await svc.set(scope="global", status=1, **item)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(init_data(reset))
