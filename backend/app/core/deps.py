"""
若茗 PaaS - FastAPI 依赖注入
提供认证、权限校验、DB Session、Redis 等通用依赖
Author: ruoming
"""
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountLockedException,
    AuthException,
    PermissionException,
    TenantDisabledException,
)
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.database import get_db

logger = structlog.get_logger(__name__)

# OAuth2 Bearer Token 提取
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    从 Bearer Token 获取当前用户。
    校验：Token 有效性 → 用户状态 → 账号锁定 → 租户状态
    """
    if not credentials:
        raise AuthException()

    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))

    # 避免循环引用，延迟 import
    from app.modules.user.models import SysUser
    from sqlalchemy import select

    result = await db.execute(
        select(SysUser).where(
            SysUser.id == user_id,
            SysUser.is_deleted == False,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthException("用户不存在")

    if not user.status:
        raise AuthException("账号已被禁用，请联系管理员")

    # 账号锁定检查
    if user.locked_until and user.locked_until > datetime.now(UTC):
        raise AccountLockedException(
            f"账号已被锁定，请在 {user.locked_until.strftime('%H:%M:%S')} 后重试"
        )

    # 非超管用户校验租户状态
    if not user.is_superplatform and user.tenant_id:
        from app.modules.tenant.models import SysTenant

        tenant_result = await db.execute(
            select(SysTenant).where(SysTenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant or tenant.status == 0:
            raise TenantDisabledException()

    # 绑定用户信息到 structlog 上下文
    structlog.contextvars.bind_contextvars(
        user_id=user.id,
        username=user.username,
    )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """可选认证（公开接口，已登录则返回用户，未登录返回 None）"""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except Exception:
        return None


def require_superplatform():
    """
    仅平台超级管理员（is_superplatform=True）可访问的接口。
    用法：Depends(require_superplatform())
    """
    async def checker(current_user=Depends(get_current_user)):
        if not current_user.is_superplatform:
            raise PermissionException("需要平台超级管理员权限")
        return current_user
    return checker


def require_permissions(*codes: str):
    """
    权限校验依赖工厂（按钮/API 级别）。
    用法：Depends(require_permissions("system:user:create"))

    校验逻辑：
    - 平台超管跳过所有权限校验
    - 其他用户检查权限码集合（含角色继承）
    """
    async def checker(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        if current_user.is_superplatform:
            return current_user

        from app.modules.permission.service import PermissionService
        perm_svc = PermissionService(db, redis)
        user_codes = await perm_svc.get_user_permission_codes(current_user.id)

        missing = [c for c in codes if c not in user_codes]
        if missing:
            raise PermissionException(f"缺少权限: {', '.join(missing)}")

        return current_user
    return checker


def require_tenant_admin():
    """
    租户管理员及以上可访问（平台超管也可访问）。
    用法：Depends(require_tenant_admin())
    """
    async def checker(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        if current_user.is_superplatform:
            return current_user
        from app.modules.permission.service import PermissionService
        perm_svc = PermissionService(db, redis)
        has_admin = await perm_svc.has_role(current_user.id, "tenant:admin")
        if not has_admin:
            raise PermissionException("需要租户管理员权限")
        return current_user
    return checker
