"""
若茗 PaaS - 租户级限流中间件

在接口级限流之上，再增加租户级限流，防止单租户过度消耗资源。
基于 Redis 实现，支持每日/每月配额，配合 slowapi 使用。

限流策略：
  - 每日 API 调用次数限制（默认 10000次/天）
  - 每日 AI Token 消耗限制（默认 100000 Token/天）
  - 并发 AI 请求限制（默认 5 个）

Author: ruoming
"""
import asyncio
from datetime import datetime
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.redis import get_redis_client, RedisKeys

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
    """
    租户级限流中间件

    在认证中间件之后运行，依赖 request.state.tenant_id 和 request.state.user_id
    """

    DEFAULT_DAILY_API_LIMIT = 10000
    DEFAULT_DAILY_TOKEN_LIMIT = 100000
    DEFAULT_CONCURRENT_AI_LIMIT = 5

    async def dispatch(self, request: Request, call_next):
        # 公开路径不做租户限流
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        redis = await get_redis_client()
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. 每日 API 调用次数限流
        api_key = RedisKeys.QUOTA_API.format(tenant_id=tenant_id, date=today)
        api_count = await redis.incr(api_key)
        if api_count == 1:
            await redis.expire(api_key, 86400)

        daily_api_limit = await self._get_tenant_config(
            redis, tenant_id, "daily_api_limit", self.DEFAULT_DAILY_API_LIMIT
        )
        if api_count > daily_api_limit:
            logger.warning(
                "tenant_api_quota_exceeded",
                tenant_id=tenant_id,
                count=api_count,
                limit=daily_api_limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": f"租户每日 API 调用次数已达上限（{daily_api_limit}次/天），请联系管理员",
                    "data": None,
                },
            )

        # 2. AI 并发请求限流（仅对 AI 推理接口）
        if "/ai/" in request.url.path and request.method == "POST":
            concurrent_key = RedisKeys.CONCURRENT_AI.format(tenant_id=tenant_id)
            concurrent_count = await redis.incr(concurrent_key)

            if concurrent_count > self.DEFAULT_CONCURRENT_AI_LIMIT:
                await redis.decr(concurrent_key)
                logger.warning(
                    "tenant_ai_concurrent_exceeded",
                    tenant_id=tenant_id,
                    count=concurrent_count,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": f"AI 并发请求已达上限（{self.DEFAULT_CONCURRENT_AI_LIMIT}个），请稍后重试",
                        "data": None,
                    },
                )

            try:
                response = await call_next(request)
            finally:
                await redis.decr(concurrent_key)
            return response

        return await call_next(request)

    async def _get_tenant_config(self, redis, tenant_id: int, key: str, default: Any) -> Any:
        """获取租户配置（优先从 Redis 缓存读取）"""
        config_key = f"tenant:config:{tenant_id}:{key}"
        cached = await redis.get(config_key)
        if cached:
            return int(cached)

        try:
            from app.database import AsyncSessionFactory
            from sqlalchemy import select
            from app.modules.tenant.models import SysTenantConfig

            async with AsyncSessionFactory() as db:
                result = await db.execute(
                    select(SysTenantConfig.value).where(
                        SysTenantConfig.tenant_id == tenant_id,
                        SysTenantConfig.key == key,
                        SysTenantConfig.is_deleted == False,
                    )
                )
                value = result.scalar_one_or_none()
                if value:
                    await redis.setex(config_key, 3600, value)
                    return int(value)
        except Exception as e:
            logger.warning("tenant_config_fetch_failed", tenant_id=tenant_id, key=key, error=str(e))

        return default