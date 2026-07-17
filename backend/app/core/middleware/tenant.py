"""
若茗 PaaS - 租户解析中间件
解析当前请求所属租户，绑定到 request.state.tenant_id
支持：JWT Token 内嵌、X-Tenant-Code 请求头、子域名解析
Author: ruoming
"""
import asyncio

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token_without_verify

logger = structlog.get_logger(__name__)

# 不需要租户解析的路径
_PUBLIC_PATHS = frozenset([
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
])


class TenantMiddleware(BaseHTTPMiddleware):
    """
    租户解析中间件（在认证中间件之前运行）

    解析优先级：
    1. JWT Token 中的 tenant_id（最常见场景）
    2. X-Tenant-Code 请求头（API 调用场景）
    3. Host 子域名（多租户 SaaS 域名场景）
    4. 无法解析 → tenant_id=None（平台级接口可用，业务接口会被后续校验拦截）

    超管代入场景：
    - is_superplatform=True 的用户可携带 X-Tenant-Impersonate 头
    - 所有代入操作自动触发审计日志（异步写入）
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.multi_tenant import is_multi_tenant_enabled

        if not await is_multi_tenant_enabled():
            request.state.tenant_id = None
            request.state.tenant_impersonated = False
        else:
            tenant_id, impersonated = await self._resolve_tenant(request)
            request.state.tenant_id = tenant_id
            request.state.tenant_impersonated = impersonated

            if tenant_id:
                structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

            if impersonated and hasattr(request.state, "user_id"):
                asyncio.create_task(
                    self._record_impersonation_audit(request, tenant_id)
                )

        response = await call_next(request)

        return response

    async def _resolve_tenant(self, request: Request) -> tuple[int | None, bool]:
        """解析租户 ID，返回 (tenant_id, is_impersonated)"""
        # 公开路径不解析租户
        if request.url.path in _PUBLIC_PATHS:
            return None, False

        token = self._extract_token(request)
        if token:
            payload = decode_token_without_verify(token)
            is_super = payload.get("sup", False)

            # 超管代入租户
            if is_super:
                impersonate_code = request.headers.get("X-Tenant-Impersonate")
                if impersonate_code:
                    tenant_id = await self._get_tenant_id_by_code(impersonate_code)
                    return tenant_id, True
                return None, False  # 超管未指定租户，访问平台级接口

            # 普通用户：从 Token 获取 tenant_id
            if tid := payload.get("tid"):
                return tid, False

        # 从请求头获取
        if code := request.headers.get("X-Tenant-Code"):
            tenant_id = await self._get_tenant_id_by_code(code)
            return tenant_id, False

        # 从子域名解析
        host = request.headers.get("host", "")
        parts = host.split(".")
        if len(parts) >= 3:  # 子域名格式：{code}.ruoming.io
            subdomain = parts[0]
            tenant_id = await self._get_tenant_id_by_code(subdomain)
            return tenant_id, False

        return None, False

    def _extract_token(self, request: Request) -> str | None:
        """从 Authorization 头提取 Bearer Token"""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    async def _get_tenant_id_by_code(self, code: str) -> int | None:
        """通过租户 code 查找 tenant_id（带 Redis 缓存）"""
        # 避免循环引用，在方法内部 import
        try:
            from app.core.redis import get_redis_client
            from app.core.redis import RedisKeys

            redis = await get_redis_client()
            cache_key = RedisKeys.TENANT_CODE_MAP.format(code=code)
            cached = await redis.get(cache_key)
            if cached:
                return int(cached)

            # 缓存未命中，查数据库
            from app.database import AsyncSessionFactory
            from sqlalchemy import select
            from app.modules.tenant.models import SysTenant

            async with AsyncSessionFactory() as db:
                result = await db.execute(
                    select(SysTenant.id).where(
                        SysTenant.code == code,
                        SysTenant.is_deleted == False,  # noqa: E712
                    )
                )
                tenant_id = result.scalar_one_or_none()

            if tenant_id:
                await redis.setex(cache_key, 3600, str(tenant_id))
            return tenant_id
        except Exception as e:
            logger.warning("tenant_resolve_failed", code=code, error=str(e))
            return None

    async def _record_impersonation_audit(self, request: Request, tenant_id: int | None) -> None:
        """记录超管代入租户的审计日志"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.audit.service import AuditService

            async with AsyncSessionFactory() as db:
                svc = AuditService(db)
                await svc.record(
                    event_type="superadmin_impersonate_tenant",
                    tenant_id=tenant_id,
                    user_id=getattr(request.state, "user_id", None),
                    detail={
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                await db.commit()
        except Exception as e:
            logger.error("impersonation_audit_failed", error=str(e))
