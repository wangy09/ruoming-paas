"""
若茗 PaaS - Redis 连接池与工具

支持三种部署模式（通过环境变量 REDIS_MODE 切换，上层业务代码无需修改）：
  - standalone（默认）：单节点，适合开发/测试
  - sentinel：哨兵模式，适合生产高可用
  - cluster：集群模式，适合高吞吐生产环境

环境变量：
  REDIS_MODE=standalone           (默认)
  REDIS_URL=redis://localhost:6379/0

  REDIS_MODE=sentinel
  REDIS_SENTINEL_HOSTS=127.0.0.1:26379,127.0.0.1:26380,127.0.0.1:26381
  REDIS_SENTINEL_MASTER=mymaster
  REDIS_SENTINEL_PASSWORD=<可选>

  REDIS_MODE=cluster
  REDIS_CLUSTER_NODES=127.0.0.1:7000,127.0.0.1:7001,127.0.0.1:7002

Author: ruoming
"""
from collections.abc import AsyncGenerator

import structlog
from redis.asyncio import Redis, from_url

from app.config import settings

logger = structlog.get_logger(__name__)

# ── 连接池单例 ────────────────────────────────────────────────────────────────
_redis_client: Redis | None = None


def _create_redis_client() -> Redis:
    """
    根据 REDIS_MODE 创建对应模式的 Redis 客户端。
    所有模式的客户端均满足 redis.asyncio.Redis 接口，上层调用方无感知。
    """
    redis_mode = getattr(settings, "REDIS_MODE", "standalone").lower()

    if redis_mode == "sentinel":
        # ── 哨兵模式 ────────────────────────────────────────────────────────
        from redis.asyncio.sentinel import Sentinel

        sentinel_hosts_raw = getattr(settings, "REDIS_SENTINEL_HOSTS", "127.0.0.1:26379")
        master_name = getattr(settings, "REDIS_SENTINEL_MASTER", "mymaster")
        sentinel_password = getattr(settings, "REDIS_SENTINEL_PASSWORD", None)

        # 解析 "host:port,host:port" 格式
        sentinels = []
        for hp in sentinel_hosts_raw.split(","):
            hp = hp.strip()
            if ":" in hp:
                host, port = hp.rsplit(":", 1)
                sentinels.append((host, int(port)))
            else:
                sentinels.append((hp, 26379))

        sentinel = Sentinel(
            sentinels,
            password=sentinel_password or None,
            sentinel_kwargs={"password": sentinel_password} if sentinel_password else {},
        )
        client = sentinel.master_for(
            master_name,
            decode_responses=True,
        )
        logger.info(
            "redis_sentinel_mode",
            master=master_name,
            sentinels=sentinels,
        )
        return client  # type: ignore[return-value]

    elif redis_mode == "cluster":
        # ── 集群模式 ─────────────────────────────────────────────────────────
        from redis.asyncio.cluster import RedisCluster
        from redis.asyncio.cluster import ClusterNode

        nodes_raw = getattr(settings, "REDIS_CLUSTER_NODES", "127.0.0.1:7000")
        startup_nodes = []
        for hp in nodes_raw.split(","):
            hp = hp.strip()
            if ":" in hp:
                host, port = hp.rsplit(":", 1)
                startup_nodes.append(ClusterNode(host, int(port)))
            else:
                startup_nodes.append(ClusterNode(hp, 7000))

        client = RedisCluster(
            startup_nodes=startup_nodes,
            decode_responses=True,
        )
        logger.info("redis_cluster_mode", startup_nodes=[str(n) for n in startup_nodes])
        return client  # type: ignore[return-value]

    else:
        # ── 单节点模式（默认）────────────────────────────────────────────────
        client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
        )
        logger.debug("redis_standalone_mode", url=settings.REDIS_URL)
        return client


async def get_redis_client() -> Redis:
    """获取全局 Redis 客户端（单例，连接池）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = _create_redis_client()
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
    CAPTCHA = "auth:captcha:{key}"                    # 验证码

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
