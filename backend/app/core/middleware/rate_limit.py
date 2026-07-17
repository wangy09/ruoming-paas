"""
若茗 PaaS - 租户级限流中间件

全局租户级 API 调用频率限制，使用 Redis 滑动窗口计数器。

限流规则从配置中心动态读取：
  - rate_limit.tenant.default: 租户级默认限流（默认 500/minute）
  - rate_limit.enabled: 是否启用限流（默认 true）

公开路径（登录、注册、验证码等）不受租户级限流限制，但仍受接口级限流保护。

Author: ruoming
"""
import time

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.rate_limit_config import is_rate_limit_enabled, get_rate_limit
from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

_PUBLIC_PATHS = frozenset([
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/captcha",
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
])


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """租户级 API 调用频率限制中间件"""

    async def dispatch(self, request: Request, call_next):
        if not await is_rate_limit_enabled():
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        try:
            limit = await get_rate_limit("tenant.default")
            max_requests, unit = self._parse_limit(limit)
            window_seconds = self._unit_to_seconds(unit)

            redis = await get_redis_client()
            window_key = f"rate:tenant:{tenant_id}:{int(time.time() // window_seconds)}"

            count = await redis.incr(window_key)
            await redis.expire(window_key, window_seconds * 2)

            if count > max_requests:
                logger.warning(
                    "tenant_rate_limit_exceeded",
                    tenant_id=tenant_id,
                    limit=limit,
                    count=count,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": "租户 API 调用频率超限，请稍后再试",
                        "data": None,
                    },
                    headers={
                        "Retry-After": str(window_seconds),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            remaining = max(0, max_requests - count)
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        except Exception as e:
            logger.warning("tenant_rate_limit_error", tenant_id=tenant_id, error=str(e))
            return await call_next(request)

    @staticmethod
    def _parse_limit(limit: str) -> tuple[int, str]:
        """解析限流配置，如 "500/minute" -> (500, "minute")"""
        parts = limit.split("/")
        if len(parts) == 2:
            return int(parts[0]), parts[1]
        return 500, "minute"

    @staticmethod
    def _unit_to_seconds(unit: str) -> int:
        """将时间单位转换为秒"""
        unit_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }
        return unit_map.get(unit.lower(), 60)