"""
若茗 PaaS - 多租户模式开关

提供全局多租户模式检查能力，支持从配置中心动态读取开关状态。

开关配置项：multi_tenant.enabled (bool)
- True: 启用多租户隔离，所有数据访问自动注入 tenant_id 过滤
- False: 关闭多租户模式，所有用户共享同一数据空间

Author: ruoming
"""
import asyncio
from typing import Callable

import structlog

from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

_CACHE_KEY = "multi_tenant:enabled"
_CACHE_TTL = 60


class MultiTenantSwitch:
    """多租户模式开关管理器"""

    def __init__(self) -> None:
        self._enabled: bool | None = None
        self._fetch_func: Callable[[], asyncio.Future[bool]] | None = None

    async def is_enabled(self) -> bool:
        """检查多租户模式是否启用

        检查优先级：
        1. 内存缓存（进程内）
        2. Redis 缓存
        3. 配置中心数据库
        """
        # 1. 内存缓存
        if self._enabled is not None:
            return self._enabled

        # 2. Redis 缓存
        try:
            redis = await get_redis_client()
            cached = await redis.get(_CACHE_KEY)
            if cached is not None:
                self._enabled = cached.lower() == "true"
                return self._enabled
        except Exception as e:
            logger.warning("multi_tenant_redis_cache_fail", error=str(e))

        # 3. 从配置中心读取
        return await self._fetch_from_config_center()

    async def _fetch_from_config_center(self) -> bool:
        """从配置中心读取开关状态"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.config_center.service import ConfigCenterService

            async with AsyncSessionFactory() as db:
                svc = ConfigCenterService(db)
                val = await svc.get("multi_tenant.enabled", scope="global")

            if val is None:
                self._enabled = True
                logger.warning("multi_tenant_config_missing", defaulting_to=True)
            else:
                self._enabled = val.lower() == "true"

            # 写入 Redis 缓存
            try:
                redis = await get_redis_client()
                await redis.setex(_CACHE_KEY, _CACHE_TTL, str(self._enabled))
            except Exception as e:
                logger.warning("multi_tenant_redis_set_fail", error=str(e))

            return self._enabled
        except Exception as e:
            logger.error("multi_tenant_fetch_fail", error=str(e))
            return True

    async def invalidate_cache(self) -> None:
        """失效缓存，下次调用会重新读取配置"""
        self._enabled = None
        try:
            redis = await get_redis_client()
            await redis.delete(_CACHE_KEY)
        except Exception as e:
            logger.warning("multi_tenant_invalidate_cache_fail", error=str(e))


_multi_tenant_switch = MultiTenantSwitch()


async def is_multi_tenant_enabled() -> bool:
    """检查多租户模式是否启用（便捷函数）"""
    return await _multi_tenant_switch.is_enabled()


async def invalidate_multi_tenant_cache() -> None:
    """失效多租户开关缓存"""
    await _multi_tenant_switch.invalidate_cache()