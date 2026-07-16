"""
若茗 PaaS - 通用熔断器模块

支持多类型服务的熔断保护：
  - LLM: AI 模型调用
  - INTEGRATION: 第三方集成（飞书、钉钉、企微）
  - WEBSEARCH: 网页搜索
  - CODEGEN: 代码生成

熔断器状态：
  - CLOSED: 正常，所有请求正常通过
  - OPEN: 熔断中，直接返回错误或切换备用
  - HALF_OPEN: 半开状态，允许少量请求尝试恢复

配置参数：
  - fail_threshold: 连续失败次数阈值（默认 5）
  - open_timeout: 熔断持续时间（秒，默认 60）
  - fail_ttl: 失败计数过期时间（秒，默认 120）

使用方式：
  from app.core.circuit_breaker import CircuitBreaker

  breaker = CircuitBreaker("llm", model_config_id)
  state = await breaker.get_state()
  if state == CircuitState.OPEN:
      # 熔断处理
      ...

  try:
      result = await external_call()
      await breaker.on_success()
      return result
  except Exception:
      await breaker.on_failure()
      raise

Author: ruoming
"""
import time
from enum import Enum
from typing import Any

import structlog
from redis.asyncio import Redis

from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitType(str, Enum):
    LLM = "llm"
    INTEGRATION = "integration"
    WEBSEARCH = "websearch"
    CODEGEN = "codegen"


class CircuitBreaker:
    def __init__(
        self,
        circuit_type: str | CircuitType,
        service_id: int | str,
        *,
        fail_threshold: int = 5,
        open_timeout: int = 60,
        fail_ttl: int = 120,
    ):
        self.circuit_type = str(circuit_type)
        self.service_id = str(service_id)
        self.fail_threshold = fail_threshold
        self.open_timeout = open_timeout
        self.fail_ttl = fail_ttl

        self.state_key = f"circuit:{self.circuit_type}:{self.service_id}:state"
        self.fail_key = f"circuit:{self.circuit_type}:{self.service_id}:fail_count"
        self.open_at_key = f"circuit:{self.circuit_type}:{self.service_id}:open_at"

    async def get_state(self) -> CircuitState:
        """获取熔断器状态"""
        try:
            redis = await get_redis_client()
            state = await redis.get(self.state_key)

            if not state or state == CircuitState.CLOSED:
                return CircuitState.CLOSED

            if state == CircuitState.OPEN:
                open_at = await redis.get(self.open_at_key)
                if open_at and (time.time() - float(open_at)) >= self.open_timeout:
                    await redis.set(self.state_key, CircuitState.HALF_OPEN, ex=self.open_timeout * 2)
                    logger.info(
                        "circuit_breaker_half_open",
                        circuit_type=self.circuit_type,
                        service_id=self.service_id,
                    )
                    return CircuitState.HALF_OPEN
                return CircuitState.OPEN

            return CircuitState(state)
        except Exception as e:
            logger.warning(
                "circuit_state_read_failed",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
                error=str(e),
            )
            return CircuitState.CLOSED

    async def on_success(self) -> None:
        """调用成功：清除失败计数，关闭熔断器"""
        try:
            redis = await get_redis_client()
            current = await redis.get(self.state_key)

            if current and current != CircuitState.CLOSED:
                logger.info(
                    "circuit_breaker_closed",
                    circuit_type=self.circuit_type,
                    service_id=self.service_id,
                )

            await redis.delete(self.state_key, self.fail_key, self.open_at_key)
        except Exception as e:
            logger.warning(
                "circuit_on_success_failed",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
                error=str(e),
            )

    async def on_failure(self) -> None:
        """调用失败：累加失败计数，达到阈值则熔断"""
        try:
            redis = await get_redis_client()

            fail_count = await redis.incr(self.fail_key)
            await redis.expire(self.fail_key, self.fail_ttl)

            if fail_count >= self.fail_threshold:
                await redis.set(self.state_key, CircuitState.OPEN, ex=self.open_timeout * 3)
                await redis.set(self.open_at_key, str(time.time()), ex=self.open_timeout * 3)
                logger.warning(
                    "circuit_breaker_opened",
                    circuit_type=self.circuit_type,
                    service_id=self.service_id,
                    fail_count=fail_count,
                )
        except Exception as e:
            logger.warning(
                "circuit_on_failure_failed",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
                error=str(e),
            )

    async def reset(self) -> None:
        """手动重置熔断器（关闭熔断）"""
        try:
            redis = await get_redis_client()
            await redis.delete(self.state_key, self.fail_key, self.open_at_key)
            logger.info(
                "circuit_breaker_reset",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
            )
        except Exception as e:
            logger.warning(
                "circuit_reset_failed",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
                error=str(e),
            )

    async def trip(self) -> None:
        """手动触发熔断（打开熔断器）"""
        try:
            redis = await get_redis_client()
            await redis.set(self.state_key, CircuitState.OPEN, ex=self.open_timeout * 3)
            await redis.set(self.open_at_key, str(time.time()), ex=self.open_timeout * 3)
            await redis.set(self.fail_key, str(self.fail_threshold), ex=self.fail_ttl)
            logger.warning(
                "circuit_breaker_tripped_manually",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
            )
        except Exception as e:
            logger.warning(
                "circuit_trip_failed",
                circuit_type=self.circuit_type,
                service_id=self.service_id,
                error=str(e),
            )


class CircuitBreakerManager:
    """熔断器管理器：提供全局查询和重置能力"""

    @staticmethod
    async def get_all_breakers() -> list[dict[str, Any]]:
        """获取所有熔断器状态（兼容新旧两种键格式）"""
        try:
            redis = await get_redis_client()

            result = []

            async for state_key in redis.scan_iter(match="circuit:*:*:state", count=100):
                parts = state_key.split(":")
                if len(parts) != 4:
                    continue

                circuit_type = parts[1]
                service_id = parts[2]

                state = await redis.get(state_key) or "CLOSED"
                fail_count = int(await redis.get(f"circuit:{circuit_type}:{service_id}:fail_count") or "0")
                open_at = await redis.get(f"circuit:{circuit_type}:{service_id}:open_at")

                data = {
                    "circuit_type": circuit_type,
                    "service_id": service_id,
                    "state": state.upper(),
                    "fail_count": fail_count,
                    "fail_threshold": 5,
                    "open_timeout": 60,
                }

                if open_at:
                    elapsed = int(time.time() - float(open_at))
                    remaining = max(0, 60 - elapsed)
                    data["open_at"] = int(float(open_at))
                    data["elapsed_seconds"] = elapsed
                    data["remaining_seconds"] = remaining

                result.append(data)

            async for state_key in redis.scan_iter(match="llm:circuit:*:state", count=100):
                parts = state_key.split(":")
                if len(parts) != 4:
                    continue

                service_id = parts[2]

                state = await redis.get(state_key) or "closed"
                fail_count = int(await redis.get(f"llm:circuit:{service_id}:fail_count") or "0")
                open_at = await redis.get(f"llm:circuit:{service_id}:open_at")

                data = {
                    "circuit_type": "llm",
                    "service_id": service_id,
                    "state": state.upper(),
                    "fail_count": fail_count,
                    "fail_threshold": 5,
                    "open_timeout": 60,
                }

                if open_at:
                    elapsed = int(time.time() - float(open_at))
                    remaining = max(0, 60 - elapsed)
                    data["open_at"] = int(float(open_at))
                    data["elapsed_seconds"] = elapsed
                    data["remaining_seconds"] = remaining

                result.append(data)

            return result
        except Exception as e:
            logger.warning("circuit_get_all_failed", error=str(e))
            return []

    @staticmethod
    async def reset_breaker(circuit_type: str, service_id: str) -> bool:
        """重置指定熔断器（关闭熔断，兼容新旧键格式）"""
        try:
            redis = await get_redis_client()
            await redis.delete(
                f"circuit:{circuit_type}:{service_id}:state",
                f"circuit:{circuit_type}:{service_id}:fail_count",
                f"circuit:{circuit_type}:{service_id}:open_at",
                f"llm:circuit:{service_id}:state",
                f"llm:circuit:{service_id}:fail_count",
                f"llm:circuit:{service_id}:open_at",
            )
            logger.info("circuit_breaker_reset", circuit_type=circuit_type, service_id=service_id)
            return True
        except Exception as e:
            logger.warning("circuit_reset_failed", circuit_type=circuit_type, service_id=service_id, error=str(e))
            return False

    @staticmethod
    async def trip_breaker(circuit_type: str, service_id: str, open_timeout: int = 60) -> bool:
        """手动触发熔断（打开熔断器，兼容新旧键格式）"""
        try:
            redis = await get_redis_client()
            await redis.set(f"circuit:{circuit_type}:{service_id}:state", CircuitState.OPEN, ex=open_timeout * 3)
            await redis.set(f"circuit:{circuit_type}:{service_id}:open_at", str(time.time()), ex=open_timeout * 3)
            await redis.set(f"circuit:{circuit_type}:{service_id}:fail_count", "5", ex=120)
            await redis.set(f"llm:circuit:{service_id}:state", "open", ex=open_timeout * 3)
            await redis.set(f"llm:circuit:{service_id}:open_at", str(time.time()), ex=open_timeout * 3)
            await redis.set(f"llm:circuit:{service_id}:fail_count", "5", ex=120)
            logger.warning("circuit_breaker_tripped_manually", circuit_type=circuit_type, service_id=service_id)
            return True
        except Exception as e:
            logger.warning("circuit_trip_failed", circuit_type=circuit_type, service_id=service_id, error=str(e))
            return False