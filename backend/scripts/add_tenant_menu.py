"""
若茗 PaaS - 添加租户管理菜单和权限（增量脚本）
Author: ruoming
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def add_tenant_menu() -> None:
    from app.core.logging import setup_logging
    from app.database import AsyncSessionFactory
    from app.modules.permission.models import SysPermission, SysRole, SysRolePermission
    from sqlalchemy import select

    setup_logging()
    import structlog
    logger = structlog.get_logger(__name__)

    async with AsyncSessionFactory() as db:
        org_parent = await db.scalar(
            select(SysPermission).where(SysPermission.code == "org")
        )
        if not org_parent:
            print("❌ 未找到组织与账号父菜单")
            return

        perms_to_add = [
            {
                "parent_id": org_parent.id,
                "name": "租户管理",
                "code": "system:tenant:menu",
                "perm_type": "menu",
                "path": "/system/tenant",
                "component": "system/tenant/index",
                "icon": "Building",
                "sort": 30,
                "is_visible": True,
                "is_cache": False,
            },
            {
                "parent_id": 0,
                "parent_code": "system:tenant:menu",
                "name": "查看租户",
                "code": "system:tenant:view",
                "perm_type": "button",
                "sort": 1,
            },
            {
                "parent_id": 0,
                "parent_code": "system:tenant:menu",
                "name": "创建租户",
                "code": "system:tenant:create",
                "perm_type": "button",
                "sort": 2,
            },
            {
                "parent_id": 0,
                "parent_code": "system:tenant:menu",
                "name": "编辑租户",
                "code": "system:tenant:update",
                "perm_type": "button",
                "sort": 3,
            },
            {
                "parent_id": 0,
                "parent_code": "system:tenant:menu",
                "name": "审核租户",
                "code": "system:tenant:approve",
                "perm_type": "button",
                "sort": 4,
            },
            {
                "parent_id": 0,
                "parent_code": "system:tenant:menu",
                "name": "删除租户",
                "code": "system:tenant:delete",
                "perm_type": "button",
                "sort": 5,
            },
        ]

        code_to_id = {}
        added_count = 0

        for p in perms_to_add:
            existing = await db.scalar(
                select(SysPermission).where(SysPermission.code == p["code"])
            )
            if existing:
                code_to_id[p["code"]] = existing.id
                print(f"  跳过已存在: {p['name']}")
                continue

            perm_data = {k: v for k, v in p.items() if k not in ("parent_code",)}
            perm = SysPermission(**perm_data)
            db.add(perm)
            await db.flush()
            code_to_id[p["code"]] = perm.id
            added_count += 1
            print(f"  添加: {p['name']}")

        for p in perms_to_add:
            if p.get("parent_code") and p["code"] not in ["system:tenant:menu"]:
                parent_id = code_to_id.get(p["parent_code"])
                if parent_id:
                    perm = await db.scalar(
                        select(SysPermission).where(SysPermission.code == p["code"])
                    )
                    if perm:
                        perm.parent_id = parent_id

        tenant_admin_role = await db.scalar(
            select(SysRole).where(SysRole.code == "tenant:admin")
        )
        if tenant_admin_role:
            for p in perms_to_add:
                perm = await db.scalar(
                    select(SysPermission).where(SysPermission.code == p["code"])
                )
                if perm:
                    existing_rp = await db.scalar(
                        select(SysRolePermission).where(
                            SysRolePermission.role_id == tenant_admin_role.id,
                            SysRolePermission.permission_id == perm.id,
                        )
                    )
                    if not existing_rp:
                        db.add(SysRolePermission(
                            role_id=tenant_admin_role.id,
                            permission_id=perm.id,
                        ))

        await db.commit()

        from app.core.redis import get_redis_client
        redis = await get_redis_client()
        await redis.delete("permission_tree_cache")
        await redis.delete("permission_code_cache")
        print("\n✅ 缓存已清理")

        print(f"\n✅ 租户管理菜单和权限添加完成！")
        print(f"   新增: {added_count} 项")
        print(f"   路径: /system/tenant")


if __name__ == "__main__":
    asyncio.run(add_tenant_menu())