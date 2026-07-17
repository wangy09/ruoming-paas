"""
若茗 PaaS - 限流模块

支持多维限流：
  - IP 级限流：防 DDoS / 爆破
  - 用户级限流：防单用户过度消耗
  - 租户级限流：防单租户拖垮系统
  - 接口级限流：高敏感接口细化控制
  - AI 推理限流：控制并发，配合 Token 配额

技术栈：slowapi + limits + Redis（分布式限流，多 Worker 共享计数器）

使用方式：
  from app.core.rate_limit import limiter, get_user_key, get_tenant_key

  @router.post("/login")
  @limiter.limit("10/minute", key_func=get_ip_key)
  async def login(request: Request, ...):
      ...

Author: ruoming
"""
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings


def get_ip_key(request: Request) -> str:
    """按 IP 限流 Key（适合未登录场景、防爆破）"""
    return f"ip:{get_remote_address(request)}"


def get_user_key(request: Request) -> str:
    """按用户限流 Key（已登录用户用 user_id，未登录用 IP）"""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_ip_key(request)


def get_tenant_key(request: Request) -> str:
    """按租户限流 Key"""
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return f"tenant:{tenant_id}"
    return get_ip_key(request)


def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """自定义限流响应格式"""
    return JSONResponse(
        status_code=429,
        content={
            "code": 429,
            "message": f"请求过于频繁，请稍后再试。限制：{exc.detail}",
            "data": None,
        },
        headers={"Retry-After": str(exc.retry_after)},
    )


limiter = Limiter(
    key_func=get_user_key,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=True,
)


def setup_rate_limit(app):
    """注册限流扩展到 FastAPI 应用"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)