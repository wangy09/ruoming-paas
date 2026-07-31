"""
增量添加反馈管理菜单和权限
执行方式: docker exec ruoming_backend python /app/scripts/add_feedback_menu.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.modules.permission.models import SysPermission


async def add_menu():
    async with AsyncSessionFactory() as db:
        # 检查菜单是否已存在
        existing = await db.execute(
            select(SysPermission).where(SysPermission.code == "ai:feedback:menu")
        )
        if existing.scalar_one_or_none():
            print("反馈管理菜单已存在，跳过")
            return

        # 获取 AI 管理父菜单的 id
        parent_result = await db.execute(
            select(SysPermission.id).where(SysPermission.code == "ai")
        )
        parent_id = parent_result.scalar_one_or_none()
        if not parent_id:
            print("未找到 AI 管理父菜单，请先执行完整初始化")
            return

        permissions = [
            # 反馈管理菜单
            SysPermission(
                parent_id=parent_id,
                name="反馈管理",
                code="ai:feedback:menu",
                perm_type="menu",
                path="/ai/feedback",
                component="ai/feedback/index",
                icon="ChatLineRound",
                sort=270,
                is_visible=True,
                is_deleted=False,
            ),
            # 查看反馈（按钮权限）
            SysPermission(
                parent_id=0,
                name="查看反馈",
                code="ai:feedback:view",
                perm_type="button",
                sort=1,
                is_visible=True,
                is_deleted=False,
            ),
            # 回复反馈（按钮权限）
            SysPermission(
                parent_id=0,
                name="回复反馈",
                code="ai:feedback:reply",
                perm_type="button",
                sort=2,
                is_visible=True,
                is_deleted=False,
            ),
            # 删除反馈（按钮权限）
            SysPermission(
                parent_id=0,
                name="删除反馈",
                code="ai:feedback:delete",
                perm_type="button",
                sort=3,
                is_visible=True,
                is_deleted=False,
            ),
        ]

        db.add_all(permissions)
        await db.commit()

        print("反馈管理菜单和权限已添加成功!")
        print("菜单路径: /ai/feedback")
        print("权限码: ai:feedback:menu / ai:feedback:view / ai:feedback:reply / ai:feedback:delete")
        print("请为角色分配权限后刷新页面查看新菜单")


if __name__ == "__main__":
    asyncio.run(add_menu())
