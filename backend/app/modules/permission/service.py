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
        menu_items = [
            self._perm_to_menu_item(p)
            for p in perms
            if p.perm_type == "menu" and p.is_visible
        ]
        menus = self._build_menu_tree(menu_items)
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
            "parent_id": perm.parent_id,
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

    def _build_menu_tree(self, menu_items: list[dict], parent_id: int = 0) -> list[dict]:
        """递归构建菜单树形结构"""
        children = [item for item in menu_items if item.get("parent_id") == parent_id]
        children.sort(key=lambda x: x.get("sort", 0))

        result = []
        for item in children:
            node = {
                **item,
                "children": self._build_menu_tree(menu_items, item["id"]),
            }
            if not node["children"]:
                node["children"] = None
            result.append(node)
        return result

    async def get_all_menus(self) -> dict[str, Any]:
        """获取所有菜单（供超管使用）"""
        result = await self.db.execute(
            select(SysPermission).where(
                SysPermission.perm_type == "menu",
                SysPermission.is_deleted == False,
            )
        )
        perms = list(result.scalars().all())
        menu_items = [self._perm_to_menu_item(p) for p in perms]
        menus = self._build_menu_tree(menu_items)
        return {
            "menus": menus,
            "columns": {},
        }

    # ── 数据权限过滤 ──────────────────────────────────────────────────

    async def get_user_data_scope_filter(self, user_id: int, user_dept_id: int | None) -> dict[str, Any]:
        """
        获取用户的数据权限过滤条件。

        返回结构：
        {
            "data_scope": 1-5,           # 最终生效的数据范围
            "allowed_dept_ids": [1,2,3], # 允许访问的部门 ID 列表
            "allowed_user_ids": [1],       # 允许访问的用户 ID 列表（仅本人时）
        }

        数据范围说明：
        - 1全部：allowed_dept_ids = None（无限制）
        - 2自定义：allowed_dept_ids = role.data_scope_depts
        - 3本部门：allowed_dept_ids = [user_dept_id]
        - 4本部门及子部门：allowed_dept_ids = [user_dept_id, ...所有子部门]
        - 5仅本人：allowed_user_ids = [user_id]
        """
        from app.modules.user.models import SysUser

        # 获取用户信息（用于判断超管）
        user_result = await self.db.execute(
            select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return {"data_scope": 5, "allowed_dept_ids": [], "allowed_user_ids": [user_id]}

        # 超管拥有所有数据权限
        if user.is_superplatform:
            return {"data_scope": 1, "allowed_dept_ids": None, "allowed_user_ids": None}

        # 获取用户所有角色的数据范围（取最大权限）
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

        if not roles:
            # 无角色，默认仅本人
            return {"data_scope": 5, "allowed_dept_ids": [], "allowed_user_ids": [user_id]}

        # 取最大的数据范围权限（1全部 > 2自定义 > 3本部门 > 4本部门及子部门 > 5仅本人）
        min_scope = min(role.data_scope for role in roles)

        # 根据最大权限范围计算过滤条件
        if min_scope == 1:
            # 全部数据
            return {"data_scope": 1, "allowed_dept_ids": None, "allowed_user_ids": None}

        if min_scope == 5:
            # 仅本人
            return {"data_scope": 5, "allowed_dept_ids": [], "allowed_user_ids": [user_id]}

        # 部门相关权限
        dept_ids: set[int] = set()

        for role in roles:
            if role.data_scope == 2:
                # 自定义部门
                if role.data_scope_depts:
                    try:
                        custom_depts = json.loads(role.data_scope_depts)
                        if isinstance(custom_depts, list):
                            dept_ids.update(custom_depts)
                    except json.JSONDecodeError:
                        pass
            elif role.data_scope == 3:
                # 本部门
                if user_dept_id:
                    dept_ids.add(user_dept_id)
            elif role.data_scope == 4:
                # 本部门及子部门
                if user_dept_id:
                    dept_ids.add(user_dept_id)
                    # 查询所有子部门
                    child_depts = await self._get_child_dept_ids(user_dept_id)
                    dept_ids.update(child_depts)

        # 合并多个角色的部门权限
        return {
            "data_scope": min_scope,
            "allowed_dept_ids": list(dept_ids) if dept_ids else [],
            "allowed_user_ids": None,
        }

    async def _get_child_dept_ids(self, parent_dept_id: int) -> list[int]:
        """递归获取所有子部门 ID"""
        from app.modules.system.models import SysDept

        child_ids: list[int] = []
        result = await self.db.execute(
            select(SysDept.id).where(
                SysDept.parent_id == parent_dept_id,
                SysDept.is_deleted == False,  # noqa: E712
            )
        )
        children = list(result.scalars().all())

        for child_id in children:
            child_ids.append(child_id)
            # 递归获取子部门的子部门
            sub_children = await self._get_child_dept_ids(child_id)
            child_ids.extend(sub_children)

        return child_ids
