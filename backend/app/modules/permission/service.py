"""
若茗 PaaS - 权限服务
包含：角色继承权限计算、用户权限聚合、权限缓存
Author: ruoming
"""
import json
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisKeys
from app.modules.permission.models import (
    SysPermission,
    SysRole,
    SysRolePermission,
    SysUserPermission,
    SysUserRole,
)

logger = structlog.get_logger(__name__)

# 权限缓存 TTL（秒）
PERM_CACHE_TTL = 30 * 60  # 30 分钟


class PermissionService:
    """权限服务"""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis

    # ── 用户权限计算 ──────────────────────────────────────────────────

    async def get_user_permission_codes(self, user_id: int) -> set[str]:
        """
        获取用户最终权限码集合（含缓存）：
        角色权限（含继承） + 用户直接授权 - 用户黑名单排除
        """
        # 尝试从 Redis 缓存获取
        cache_key = RedisKeys.USER_PERMISSIONS.format(user_id=user_id)
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return set(data.get("codes", []))

        codes = await self._compute_user_permissions(user_id)

        # 写缓存
        cache_data = {"codes": list(codes)}
        await self.redis.setex(cache_key, PERM_CACHE_TTL, json.dumps(cache_data))

        return codes

    async def get_user_full_permissions(self, user_id: int) -> dict[str, Any]:
        """
        获取用户完整权限数据（含菜单、按钮、列权限）。
        前端初始化使用（登录后一次性拉取）。
        """
        cache_key = RedisKeys.USER_PERMISSIONS.format(user_id=user_id)
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        codes = await self._compute_user_permissions(user_id)

        # 获取所有权限详情（按类型分类）
        perm_result = await self.db.execute(
            select(SysPermission).where(
                SysPermission.code.in_(codes),
                SysPermission.is_deleted == False,  # noqa: E712
            )
        )
        perms = list(perm_result.scalars().all())

        buttons = [p.code for p in perms if p.perm_type == "button"]
        menus = [
            self._perm_to_menu_item(p)
            for p in perms
            if p.perm_type == "menu" and p.is_visible
        ]
        # 列权限（resourceKey -> 可见列名列表）
        columns: dict[str, list[str]] = {}
        for p in perms:
            if p.perm_type == "column" and p.resource:
                col_name = p.code.split(":")[-1]  # e.g. system:user:column:phone -> phone
                columns.setdefault(p.resource, []).append(col_name)

        full_data = {
            "codes": list(codes),
            "buttons": buttons,
            "menus": menus,
            "columns": columns,
        }

        await self.redis.setex(cache_key, PERM_CACHE_TTL, json.dumps(full_data, default=str))
        return full_data

    async def has_role(self, user_id: int, role_code: str) -> bool:
        """检查用户是否拥有指定角色"""
        result = await self.db.execute(
            select(SysUserRole.role_id)
            .join(SysRole, SysRole.id == SysUserRole.role_id)
            .where(
                SysUserRole.user_id == user_id,
                SysRole.code == role_code,
                SysRole.status == 1,
                SysRole.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None

    async def invalidate_user_permission_cache(self, user_id: int) -> None:
        """使用户权限缓存失效（权限变更时调用）"""
        cache_key = RedisKeys.USER_PERMISSIONS.format(user_id=user_id)
        await self.redis.delete(cache_key)

    async def invalidate_role_users_cache(self, role_id: int) -> None:
        """使某角色下所有用户的权限缓存失效"""
        result = await self.db.execute(
            select(SysUserRole.user_id).where(SysUserRole.role_id == role_id)
        )
        user_ids = [row[0] for row in result.all()]
        if user_ids:
            keys = [RedisKeys.USER_PERMISSIONS.format(user_id=uid) for uid in user_ids]
            await self.redis.delete(*keys)

    # ── 角色权限计算（含继承）────────────────────────────────────────

    async def get_role_permission_codes(self, role_id: int) -> set[str]:
        """递归获取角色（含父角色继承链）的全部权限码"""
        role_result = await self.db.execute(
            select(SysRole).where(
                SysRole.id == role_id,
                SysRole.is_deleted == False,  # noqa: E712
            )
        )
        role = role_result.scalar_one_or_none()
        if not role:
            return set()

        codes: set[str] = set()

        # 先获取父角色权限（递归，防止循环继承最多 10 层）
        if role.parent_id and role.parent_id != 0:
            parent_codes = await self.get_role_permission_codes(role.parent_id)
            codes.update(parent_codes)

        # 再获取本角色权限（叠加，优先级高于父角色）
        own_codes = await self._get_role_own_permission_codes(role_id)
        codes.update(own_codes)

        return codes

    async def _get_role_own_permission_codes(self, role_id: int) -> list[str]:
        """获取角色自身（不含继承）的权限码"""
        result = await self.db.execute(
            select(SysPermission.code)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .where(
                SysRolePermission.role_id == role_id,
                SysPermission.is_deleted == False,  # noqa: E712
            )
        )
        return [row[0] for row in result.all()]

    async def _compute_user_permissions(self, user_id: int) -> set[str]:
        """计算用户最终权限集合（不经缓存，直接计算）"""
        # 1. 获取用户所有角色
        roles_result = await self.db.execute(
            select(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .where(
                SysUserRole.user_id == user_id,
                SysRole.status == 1,
                SysRole.is_deleted == False,  # noqa: E712
            )
        )
        roles = list(roles_result.scalars().all())

        codes: set[str] = set()
        for role in roles:
            role_codes = await self.get_role_permission_codes(role.id)
            codes.update(role_codes)

        # 2. 加上用户直接授权（白名单）
        direct_result = await self.db.execute(
            select(SysPermission.code)
            .join(SysUserPermission, SysUserPermission.permission_id == SysPermission.id)
            .where(
                SysUserPermission.user_id == user_id,
                SysUserPermission.is_exclude == False,  # noqa: E712
                SysPermission.is_deleted == False,  # noqa: E712
            )
        )
        direct_codes = {row[0] for row in direct_result.all()}
        codes.update(direct_codes)

        # 3. 减去用户排除权限（黑名单）
        exclude_result = await self.db.execute(
            select(SysPermission.code)
            .join(SysUserPermission, SysUserPermission.permission_id == SysPermission.id)
            .where(
                SysUserPermission.user_id == user_id,
                SysUserPermission.is_exclude == True,  # noqa: E712
                SysPermission.is_deleted == False,  # noqa: E712
            )
        )
        exclude_codes = {row[0] for row in exclude_result.all()}
        codes -= exclude_codes

        return codes

    def _perm_to_menu_item(self, perm: SysPermission) -> dict:
        """将权限对象转换为前端菜单结构"""
        return {
            "id": perm.id,
            "parentId": perm.parent_id,
            "title": perm.name,
            "path": perm.path,
            "component": perm.component,
            "redirect": perm.redirect,
            "icon": perm.icon,
            "sort": perm.sort,
            "isVisible": perm.is_visible,
            "isCache": perm.is_cache,
            "isExternal": perm.is_external,
            "permissionCode": perm.code,
        }
