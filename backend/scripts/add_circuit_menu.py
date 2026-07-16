"""
增量添加熔断器监控菜单和权限
执行方式: docker exec ruoming_backend python /app/scripts/add_circuit_menu.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text

from app.database import AsyncSessionFactory
from app.modules.permission.models import SysPermission


async def add_menu():
    async with AsyncSessionFactory() as db:
        # 检查菜单是否已存在
        existing = await db.execute(
            select(SysPermission).where(SysPermission.code == "monitor:circuit:menu")
        )
        if existing.scalar_one_or_none():
            print("熔断器监控菜单已存在，跳过")
            return

        # 获取系统监控父菜单的 id
        parent_result = await db.execute(
            select(SysPermission.id).where(SysPermission.code == "monitor")
        )
        parent_id = parent_result.scalar_one_or_none()
        if not parent_id:
            print("未找到系统监控父菜单，请先执行完整初始化")
            return

        permissions = [
            SysPermission(
                parent_id=parent_id,
                parent_code="monitor",
                name="熔断器监控",
                code="monitor:circuit:menu",
                perm_type="menu",
                path="/monitor/circuit",
                component="monitor/circuit/index",
                icon="Shield",
                sort=430,
                is_visible=True,
                is_deleted=False,
            ),
            SysPermission(
                parent_id=0,
                parent_code="monitor:circuit:menu",
                name="查看熔断器",
                code="monitor:circuit:view",
                perm_type="button",
                sort=1,
                is_visible=True,
                is_deleted=False,
            ),
            SysPermission(
                parent_id=0,
                parent_code="monitor:circuit:menu",
                name="重置熔断器",
                code="monitor:circuit:reset",
                perm_type="button",
                sort=2,
                is_visible=True,
                is_deleted=False,
            ),
            SysPermission(
                parent_id=0,
                parent_code="monitor:circuit:menu",
                name="触发熔断",
                code="monitor:circuit:trip",
                perm_type="button",
                sort=3,
                is_visible=True,
                is_deleted=False,
            ),
        ]

        db.add_all(permissions)
        await db.commit()

        print("熔断器监控菜单和权限已添加成功!")
        print("请刷新页面查看新菜单")


if __name__ == "__main__":
    asyncio.run(add_menu())