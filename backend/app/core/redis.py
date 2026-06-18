"""
若茗 PaaS - Redis 连接池与工具
Author: ruoming
"""
from collections.abc import AsyncGenerator

import structlog
from redis.asyncio import Redis, from_url

from app.config import settings

logger = structlog.get_logger(__name__)

# ── 连接池单例 ────────────────────────────────────────────────────────────────
_redis_client: Redis | None = None


async def get_redis_client() -> Redis:
    """获取全局 Redis 客户端（连接池）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
        )
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接池"""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("redis_connection_closed")


# ── FastAPI 依赖注入 ──────────────────────────────────────────────────────────
async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI 依赖：提供 Redis 客户端"""
    redis = await get_redis_client()
    yield redis


# ── 常用 Redis Key 前缀常量 ───────────────────────────────────────────────────
class RedisKeys:
    # 认证
    REFRESH_TOKEN = "auth:refresh:{jti}"             # Refresh Token 白名单
    ACCESS_TOKEN_BLACKLIST = "auth:blacklist:{jti}"  # Access Token 黑名单
    LOGIN_FAIL = "auth:login_fail:{username}"         # 登录失败次数
    LOGIN_LOCK = "auth:login_lock:{username}"         # 账号锁定标记

    # 权限缓存
    USER_PERMISSIONS = "perm:user:{user_id}"         # 用户权限缓存

    # 配额计数器
    QUOTA_API = "quota:api:{tenant_id}:{date}"       # 租户每日 API 调用次数
    QUOTA_AI_TOKEN = "quota:ai_token:{tenant_id}:{date}"  # 租户每日 AI Token
    CONCURRENT_AI = "concurrent:ai:{tenant_id}"      # AI 并发计数

    # 租户信息缓存
    TENANT_INFO = "tenant:info:{tenant_id}"
    TENANT_CODE_MAP = "tenant:code:{code}"           # code -> tenant_id

    # 配置中心
    CONFIG_CACHE = "config:{scope}:{tenant_id}:{app_key}:{user_id}"

    @classmethod
    def format(cls, template: str, **kwargs) -> str:
        return template.format(**kwargs)
