"""
若茗 PaaS - 初始化种子数据
首次启动后执行，创建：超管账号、默认租户、基础权限数据
Author: ruoming
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def init_data() -> None:
    from app.config import settings
    from app.core.logging import setup_logging
    from app.core.security import hash_password
    from app.database import AsyncSessionFactory
    from app.modules.permission.models import (
        SysPermission, SysRole, SysRolePermission, SysUserRole,
    )
    from app.modules.tenant.models import SysTenant
    from app.modules.user.models import SysUser
    from sqlalchemy import select

    setup_logging()

    import structlog
    logger = structlog.get_logger(__name__)

    async with AsyncSessionFactory() as db:
        # ── 1. 检查是否已初始化 ────────────────────────────────────────
        existing = await db.execute(
            select(SysUser).where(SysUser.is_superplatform == True)  # noqa: E712
        )
        if existing.scalar_one_or_none():
            logger.info("already_initialized", msg="种子数据已存在，跳过初始化")
            return

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
            tenant_id=None,  # 角色模板（平台级）
        )
        db.add(tenant_admin_role)

        normal_role = SysRole(
            name="普通用户",
            code="tenant:user",
            description="普通成员，基本查看权限",
            parent_id=0,
            data_scope=4,   # 仅本人
            status=1,
            sort=10,
            tenant_id=None,
        )
        db.add(normal_role)
        await db.flush()

        # ── 5. 创建基础权限数据 ───────────────────────────────────────
        permissions_data = _get_default_permissions()
        perm_objects = []
        for p in permissions_data:
            perm = SysPermission(**p)
            db.add(perm)
            perm_objects.append(perm)
        await db.flush()

        # 给租户管理员角色分配所有权限
        for perm in perm_objects:
            db.add(SysRolePermission(
                role_id=tenant_admin_role.id,
                permission_id=perm.id,
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
    return [
        # ── 系统管理（根菜单）────────────────────────────────────────
        {
            "parent_id": 0, "name": "系统管理", "code": "system",
            "perm_type": "menu", "path": "/system", "component": "",
            "icon": "Setting", "sort": 100, "is_visible": True,
        },
        # 用户管理菜单
        {
            "parent_id": 0, "name": "用户管理", "code": "system:user:menu",
            "perm_type": "menu", "path": "/system/user",
            "component": "system/user/index", "icon": "User", "sort": 110, "is_visible": True,
        },
        # 用户按钮权限
        {"parent_id": 0, "name": "查询用户", "code": "system:user:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "name": "新增用户", "code": "system:user:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "name": "编辑用户", "code": "system:user:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "name": "删除用户", "code": "system:user:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "name": "重置密码", "code": "system:user:reset_pwd", "perm_type": "button", "sort": 5},
        {"parent_id": 0, "name": "分配角色", "code": "system:user:assign_role", "perm_type": "button", "sort": 6},
        {"parent_id": 0, "name": "导出用户", "code": "system:user:export", "perm_type": "button", "sort": 7},
        # 角色管理菜单
        {
            "parent_id": 0, "name": "角色管理", "code": "system:role:menu",
            "perm_type": "menu", "path": "/system/role",
            "component": "system/role/index", "icon": "UserFilled", "sort": 120, "is_visible": True,
        },
        {"parent_id": 0, "name": "查询角色", "code": "system:role:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "name": "新增角色", "code": "system:role:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "name": "编辑角色", "code": "system:role:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "name": "删除角色", "code": "system:role:delete", "perm_type": "button", "sort": 4},
        {"parent_id": 0, "name": "分配权限", "code": "system:role:assign_perm", "perm_type": "button", "sort": 5},
        # 权限管理菜单
        {
            "parent_id": 0, "name": "权限管理", "code": "system:permission:menu",
            "perm_type": "menu", "path": "/system/permission",
            "component": "system/permission/index", "icon": "Lock", "sort": 130, "is_visible": True,
        },
        {"parent_id": 0, "name": "查询权限", "code": "system:permission:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "name": "新增权限", "code": "system:permission:create", "perm_type": "button", "sort": 2},
        {"parent_id": 0, "name": "编辑权限", "code": "system:permission:update", "perm_type": "button", "sort": 3},
        {"parent_id": 0, "name": "删除权限", "code": "system:permission:delete", "perm_type": "button", "sort": 4},
        # 审计日志菜单
        {
            "parent_id": 0, "name": "审计日志", "code": "system:audit:menu",
            "perm_type": "menu", "path": "/system/audit",
            "component": "system/audit/index", "icon": "Document", "sort": 190, "is_visible": True,
        },
        {"parent_id": 0, "name": "查询审计日志", "code": "system:audit:view", "perm_type": "button", "sort": 1},
        {"parent_id": 0, "name": "导出审计日志", "code": "system:audit:export", "perm_type": "button", "sort": 2},
        # ── AI 管理（根菜单）─────────────────────────────────────────
        {
            "parent_id": 0, "name": "AI 管理", "code": "ai",
            "perm_type": "menu", "path": "/ai", "component": "",
            "icon": "MagicStick", "sort": 200, "is_visible": True,
        },
        {
            "parent_id": 0, "name": "模型管理", "code": "ai:model:menu",
            "perm_type": "menu", "path": "/ai/model",
            "component": "ai/model/index", "icon": "Cpu", "sort": 210, "is_visible": True,
        },
        {
            "parent_id": 0, "name": "Agent 管理", "code": "ai:agent:menu",
            "perm_type": "menu", "path": "/ai/agent",
            "component": "ai/agent/index", "icon": "Robot", "sort": 220, "is_visible": True,
        },
        {
            "parent_id": 0, "name": "知识库", "code": "ai:knowledge:menu",
            "perm_type": "menu", "path": "/ai/knowledge",
            "component": "ai/knowledge/index", "icon": "Reading", "sort": 230, "is_visible": True,
        },
        # ── 列权限示例 ────────────────────────────────────────────────
        {"parent_id": 0, "name": "用户手机号列", "code": "system:user:column:phone",
         "perm_type": "column", "resource": "user_list", "sort": 1},
        {"parent_id": 0, "name": "用户邮箱列", "code": "system:user:column:email",
         "perm_type": "column", "resource": "user_list", "sort": 2},
    ]


if __name__ == "__main__":
    asyncio.run(init_data())
