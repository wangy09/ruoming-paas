"""
若茗 PaaS - 可配置限流服务

支持从配置中心动态读取限流规则，无需重启服务即可调整限流策略。

配置项：
  - rate_limit.enabled: 是否启用限流（默认 true）
  - rate_limit.global.default: 全局默认限流（默认 100/minute）
  - rate_limit.ip.default: IP 级默认限流（默认 300/minute）
  - rate_limit.user.default: 用户级默认限流（默认 60/minute）
  - rate_limit.tenant.default: 租户级默认限流（默认 500/minute）
  - rate_limit.api.login: 登录接口限流（默认 10/minute）
  - rate_limit.api.register: 注册接口限流（默认 5/minute）
  - rate_limit.api.captcha: 验证码接口限流（默认 3/minute）
  - rate_limit.ai.chat: AI 对话限流（默认 30/minute）
  - rate_limit.ai.agent: AI Agent 执行限流（默认 30/minute）

使用方式：
  from app.core.rate_limit_config import RateLimitConfig

  config = RateLimitConfig()
  limit = await config.get_limit("api.login")
  # 返回 "10/minute"

Author: ruoming
"""
import asyncio
import time
from typing import Dict, Optional

import structlog

from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

_CACHE_KEY = "rate_limit:config"
_CACHE_TTL = 60


class RateLimitConfig:
    """可配置的限流规则管理器"""

    _DEFAULTS = {
        "rate_limit.enabled": "true",
        "rate_limit.global.default": "100/minute",
        "rate_limit.ip.default": "300/minute",
        "rate_limit.user.default": "60/minute",
        "rate_limit.tenant.default": "500/minute",
        "rate_limit.api.login": "10/minute",
        "rate_limit.api.register": "5/minute",
        "rate_limit.api.captcha": "3/minute",
        "rate_limit.ai.chat": "30/minute",
        "rate_limit.ai.agent": "30/minute",
    }

    def __init__(self) -> None:
        self._config: Dict[str, str] = {}
        self._last_load: float = 0

    async def is_enabled(self) -> bool:
        """检查限流是否启用"""
        val = await self.get("rate_limit.enabled")
        return val.lower() == "true"

    async def get(self, key: str, default: Optional[str] = None) -> str:
        """获取指定限流配置"""
        await self._ensure_loaded()
        return self._config.get(key, default or self._DEFAULTS.get(key, "100/minute"))

    async def get_limit(self, rule_name: str) -> str:
        """获取指定规则的限流值"""
        key = f"rate_limit.{rule_name}"
        return await self.get(key)

    async def get_global_limit(self) -> str:
        """获取全局默认限流"""
        return await self.get("rate_limit.global.default")

    async def get_ip_limit(self) -> str:
        """获取 IP 级默认限流"""
        return await self.get("rate_limit.ip.default")

    async def get_user_limit(self) -> str:
        """获取用户级默认限流"""
        return await self.get("rate_limit.user.default")

    async def get_tenant_limit(self) -> str:
        """获取租户级默认限流"""
        return await self.get("rate_limit.tenant.default")

    async def _ensure_loaded(self) -> None:
        """确保配置已加载，超过 TTL 则重新加载"""
        now = time.time()
        if now - self._last_load > _CACHE_TTL or not self._config:
            await self._load_config()

    async def _load_config(self) -> None:
        """从 Redis 缓存或配置中心加载配置"""
        try:
            redis = await get_redis_client()
            cached = await redis.hgetall(_CACHE_KEY)

            if cached:
                self._config = dict(self._DEFAULTS)
                self._config.update({k.decode(): v.decode() for k, v in cached.items()})
                self._last_load = time.time()
                return
        except Exception as e:
            logger.warning("rate_limit_redis_cache_fail", error=str(e))

        await self._load_from_config_center()

    async def _load_from_config_center(self) -> None:
        """从配置中心数据库加载限流配置"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.config_center.service import ConfigCenterService

            async with AsyncSessionFactory() as db:
                svc = ConfigCenterService(db)
                keys = list(self._DEFAULTS.keys())
                values = await svc.get_merged(keys, tenant_id=None, app_key=None, user_id=None)

            self._config = dict(self._DEFAULTS)
            for key in keys:
                if values.get(key):
                    self._config[key] = values[key]

            self._last_load = time.time()

            try:
                redis = await get_redis_client()
                await redis.hset(_CACHE_KEY, mapping=self._config)
                await redis.expire(_CACHE_KEY, _CACHE_TTL)
            except Exception as e:
                logger.warning("rate_limit_redis_set_fail", error=str(e))

        except Exception as e:
            logger.error("rate_limit_load_fail", error=str(e))
            self._config = dict(self._DEFAULTS)

    async def invalidate_cache(self) -> None:
        """失效缓存，下次调用会重新加载"""
        self._last_load = 0
        self._config = {}
        try:
            redis = await get_redis_client()
            await redis.delete(_CACHE_KEY)
        except Exception as e:
            logger.warning("rate_limit_invalidate_cache_fail", error=str(e))


_rate_limit_config = RateLimitConfig()


async def is_rate_limit_enabled() -> bool:
    """检查限流是否启用（便捷函数）"""
    return await _rate_limit_config.is_enabled()


async def get_rate_limit(rule_name: str) -> str:
    """获取指定规则的限流值（便捷函数）"""
    return await _rate_limit_config.get_limit(rule_name)


async def invalidate_rate_limit_cache() -> None:
    """失效限流配置缓存（便捷函数）"""
    await _rate_limit_config.invalidate_cache()