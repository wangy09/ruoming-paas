"""
若茗 PaaS - LLM 网关服务层
职责：
  1. 根据 AiModelConfig 实例化并缓存 Provider（进程内缓存 + Redis Pub/Sub 多 Worker 失效）
  2. 统一对话入口，自动记录调用日志（ai_call_log）
  3. 向量化代理
  4. 三状态熔断器（CLOSED → OPEN → HALF_OPEN），主力模型故障自动切换备用模型
  5. 语义缓存（Redis Hash，按 hash(model_id+messages) 做 key，TTL 可配）
Author: ruoming
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from enum import Enum
from typing import TYPE_CHECKING, AsyncGenerator

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.models import AiModelConfig
from app.ai.llm.providers.base import BaseLLMProvider, ChatMessage, ChatResult
from app.ai.llm.providers.openai_compat import OpenAICompatProvider
from app.ai.llm.providers.zhuilu import ZhuiluProvider
from app.config import settings
from app.core.security import decrypt_value

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


# ── Redis 辅助（复用全局连接池，避免 service 内每次新建连接）────────────────────

async def _get_redis():
    from app.core.redis import get_redis_client
    return await get_redis_client()


# ── 三状态熔断器 ──────────────────────────────────────────────────────────────

class CircuitState(str, Enum):
    CLOSED = "closed"        # 正常，放行请求
    OPEN = "open"            # 熔断，直接拒绝
    HALF_OPEN = "half_open"  # 探测，放行一次试探


# Redis Key 模板
_CIRCUIT_STATE_KEY = "llm:circuit:{model_config_id}:state"
_CIRCUIT_FAIL_KEY  = "llm:circuit:{model_config_id}:fail_count"
_CIRCUIT_OPEN_AT   = "llm:circuit:{model_config_id}:open_at"

# 熔断参数（可后续迁移到 config_center 做租户级配置）
_CIRCUIT_FAIL_THRESHOLD = 5    # 连续失败次数达到此值触发熔断
_CIRCUIT_OPEN_TIMEOUT   = 60   # 熔断持续秒数，超过后进入 HALF_OPEN
_CIRCUIT_FAIL_TTL       = 120  # 失败计数 TTL（秒），超时自动重置

# 语义缓存参数
_SEMANTIC_CACHE_TTL_DEFAULT = 3600  # 默认 1 小时

# Redis Pub/Sub 频道：模型配置变更通知
_PROVIDER_CACHE_CHANNEL = "ruoming:llm:config:invalidate"


class LLMService:
    """
    LLM 统一网关服务。

    Provider 实例缓存在进程内字典（_providers）中，
    多 Worker 通过 Redis Pub/Sub 同步失效，保证配置变更实时生效。
    """

    # 进程内 Provider 缓存（key = model_config_id）
    _providers: dict[int, BaseLLMProvider] = {}
    # 模型配置缓存（避免重复查 DB）
    _configs: dict[int, AiModelConfig] = {}

    # ── 缓存管理 ──────────────────────────────────────────────────────────────

    @classmethod
    async def invalidate_provider(cls, model_config_id: int) -> None:
        """清除指定 ID 的进程内 Provider & 配置缓存"""
        cls._providers.pop(model_config_id, None)
        cls._configs.pop(model_config_id, None)

    @classmethod
    async def start_invalidation_listener(cls) -> None:
        """
        应用启动时调用，启动后台协程监听 Redis Pub/Sub。
        当模型配置被修改时，各 Worker 自动清除本地缓存。
        """

        async def _listen() -> None:
            try:
                redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                pubsub = redis.pubsub()
                await pubsub.subscribe(_PROVIDER_CACHE_CHANNEL)
                async for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        try:
                            config_id = int(message["data"])
                            await cls.invalidate_provider(config_id)
                            logger.info("llm_provider_cache_invalidated", model_config_id=config_id)
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.error("llm_invalidation_listener_error", error=str(e))

        asyncio.create_task(_listen(), name="llm_config_listener")

    @classmethod
    async def notify_config_changed(cls, model_config_id: int) -> None:
        """模型配置变更时调用，广播给所有 Worker（通过 Redis Pub/Sub）"""
        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis.publish(_PROVIDER_CACHE_CHANNEL, str(model_config_id))
            # 同时清除本 Worker 缓存
            await cls.invalidate_provider(model_config_id)
        except Exception as e:
            logger.warning("llm_notify_config_changed_failed", error=str(e))
        finally:
            await redis.aclose()

    # ── Provider 获取 ─────────────────────────────────────────────────────────

    @classmethod
    async def get_provider(cls, model_config_id: int, db: AsyncSession) -> BaseLLMProvider:
        """根据配置 ID 获取（并缓存）Provider 实例"""
        if model_config_id not in cls._providers:
            config = await cls._load_config(model_config_id, db)
            cls._providers[model_config_id] = cls._build_provider(config)
        return cls._providers[model_config_id]

    @classmethod
    async def get_default_provider(cls, db: AsyncSession, embed: bool = False) -> tuple[BaseLLMProvider, AiModelConfig]:
        """获取默认对话/向量化模型的 Provider"""
        stmt = (
            select(AiModelConfig)
            .where(AiModelConfig.is_deleted == False)
            .where(AiModelConfig.status == 1)
        )
        if embed:
            stmt = stmt.where(AiModelConfig.is_embed == True)
        else:
            stmt = stmt.where(AiModelConfig.is_default == True).where(AiModelConfig.is_embed == False)

        result = await db.execute(stmt)
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError("未找到可用的默认模型配置，请先在后台添加模型")

        provider = cls._build_provider(config)
        return provider, config

    @classmethod
    async def _load_config(cls, model_config_id: int, db: AsyncSession) -> AiModelConfig:
        if model_config_id in cls._configs:
            return cls._configs[model_config_id]
        config = await db.get(AiModelConfig, model_config_id)
        if not config or config.is_deleted:
            raise ValueError(f"模型配置 ID={model_config_id} 不存在或已删除")
        cls._configs[model_config_id] = config
        return config

    @staticmethod
    def _build_provider(config: AiModelConfig) -> BaseLLMProvider:
        """根据配置构建 Provider 实例。
        
        路由策略：优先按 protocol 字段判断通信协议；
        对 openai_compat 协议，再用 provider 字段匹配内置厂商默认 base_url。
        这样支持任意厂商（阿里云通义/豆包/DeepSeek 等），无需改代码。
        """
        raw_key = decrypt_value(config.api_key) if config.api_key else ""
        protocol = getattr(config, "protocol", None) or "openai_compat"

        # 内置厂商默认 base_url（仅在用户未填写时作为兜底）
        _VENDOR_BASE_URLS: dict[str, str] = {
            "zhuilu":   getattr(settings, "ZHUILU_BASE_URL", ""),
            "openai":   getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "ollama":   getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
            "azure":    "",
            "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "doubao":   "https://ark.cn-beijing.volces.com/api/v3",
            "deepseek": "https://api.deepseek.com/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "zhipu":    "https://open.bigmodel.cn/api/paas/v4",
            "minimax":  "https://api.minimax.chat/v1",
            "baidu":    "https://qianfan.baidubce.com/v2",
        }

        fallback_url = _VENDOR_BASE_URLS.get(config.provider, "")
        base_url = config.base_url or fallback_url

        match protocol:
            case "openai_compat":
                # 追鹿使用专属 Provider（有自定义 headers），其余统一走 OpenAICompatProvider
                if config.provider == "zhuilu":
                    return ZhuiluProvider(api_key=raw_key, base_url=base_url)
                # ollama 本地部署通常无需 api_key
                effective_key = raw_key if config.provider != "ollama" else (raw_key or "ollama")
                return OpenAICompatProvider(
                    api_key=effective_key,
                    base_url=base_url,
                    provider_name=config.provider,
                )
            case _:
                # anthropic / gemini 等协议暂未实现，降级到 openai_compat 并记录警告
                logger.warning(
                    "unsupported_protocol_fallback",
                    provider=config.provider,
                    protocol=protocol,
                    note="协议暂未实现，降级为 openai_compat",
                )
                return OpenAICompatProvider(
                    api_key=raw_key,
                    base_url=base_url,
                    provider_name=config.provider,
                )

    # ── 熔断器方法 ────────────────────────────────────────────────────────────

    @classmethod
    async def _get_circuit_state(cls, model_config_id: int) -> CircuitState:
        """获取熔断器状态（从 Redis 读取）"""
        try:
            redis = await _get_redis()
            state_key = _CIRCUIT_STATE_KEY.format(model_config_id=model_config_id)
            open_at_key = _CIRCUIT_OPEN_AT.format(model_config_id=model_config_id)

            state = await redis.get(state_key)
            if not state or state == CircuitState.CLOSED:
                return CircuitState.CLOSED

            if state == CircuitState.OPEN:
                # 检查是否超过熔断超时时间，若超过则进入 HALF_OPEN
                open_at = await redis.get(open_at_key)
                if open_at and (time.time() - float(open_at)) >= _CIRCUIT_OPEN_TIMEOUT:
                    await redis.set(state_key, CircuitState.HALF_OPEN, ex=_CIRCUIT_OPEN_TIMEOUT * 2)
                    logger.info("circuit_breaker_half_open", model_config_id=model_config_id)
                    return CircuitState.HALF_OPEN
                return CircuitState.OPEN

            return CircuitState(state)
        except Exception as e:
            logger.warning("circuit_state_read_failed", error=str(e))
            return CircuitState.CLOSED  # 读取失败默认放行

    @classmethod
    async def _on_call_success(cls, model_config_id: int) -> None:
        """调用成功：清除失败计数，关闭熔断器"""
        try:
            redis = await _get_redis()
            state_key = _CIRCUIT_STATE_KEY.format(model_config_id=model_config_id)
            fail_key  = _CIRCUIT_FAIL_KEY.format(model_config_id=model_config_id)
            open_at_key = _CIRCUIT_OPEN_AT.format(model_config_id=model_config_id)

            current = await redis.get(state_key)
            if current and current != CircuitState.CLOSED:
                logger.info("circuit_breaker_closed", model_config_id=model_config_id)

            await redis.delete(state_key, fail_key, open_at_key)
        except Exception as e:
            logger.warning("circuit_on_success_failed", error=str(e))

    @classmethod
    async def _on_call_failure(cls, model_config_id: int) -> None:
        """调用失败：累加失败计数，达到阈值则熔断"""
        try:
            redis = await _get_redis()
            fail_key  = _CIRCUIT_FAIL_KEY.format(model_config_id=model_config_id)
            state_key = _CIRCUIT_STATE_KEY.format(model_config_id=model_config_id)
            open_at_key = _CIRCUIT_OPEN_AT.format(model_config_id=model_config_id)

            fail_count = await redis.incr(fail_key)
            await redis.expire(fail_key, _CIRCUIT_FAIL_TTL)

            if fail_count >= _CIRCUIT_FAIL_THRESHOLD:
                await redis.set(state_key, CircuitState.OPEN, ex=_CIRCUIT_OPEN_TIMEOUT * 3)
                await redis.set(open_at_key, str(time.time()), ex=_CIRCUIT_OPEN_TIMEOUT * 3)
                logger.warning(
                    "circuit_breaker_opened",
                    model_config_id=model_config_id,
                    fail_count=fail_count,
                )
        except Exception as e:
            logger.warning("circuit_on_failure_failed", error=str(e))

    @classmethod
    async def _get_fallback_config(cls, db: AsyncSession, primary_config_id: int) -> AiModelConfig | None:
        """获取备用模型（is_fallback=True）"""
        try:
            stmt = (
                select(AiModelConfig)
                .where(AiModelConfig.is_deleted == False)
                .where(AiModelConfig.status == 1)
                .where(AiModelConfig.is_fallback == True)  # noqa: E712
                .where(AiModelConfig.id != primary_config_id)
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception:
            return None

    # ── 语义缓存方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_cache_key(model_config_id: int, messages: list[ChatMessage]) -> str:
        """生成语义缓存 key：hash(model_id + messages_text)"""
        messages_text = json.dumps(
            [{"role": m.role, "content": m.content} for m in messages],
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(f"{model_config_id}:{messages_text}".encode()).hexdigest()
        return f"llm:semantic_cache:{digest}"

    @classmethod
    async def _get_from_cache(cls, cache_key: str) -> ChatResult | None:
        """从 Redis 缓存中获取结果"""
        try:
            redis = await _get_redis()
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ChatResult(**data)
        except Exception as e:
            logger.debug("semantic_cache_get_failed", error=str(e))
        return None

    @classmethod
    async def _set_to_cache(cls, cache_key: str, result: ChatResult, ttl: int) -> None:
        """将结果写入 Redis 缓存"""
        try:
            redis = await _get_redis()
            data = {
                "content": result.content,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
            }
            await redis.set(cache_key, json.dumps(data, ensure_ascii=False), ex=ttl)
        except Exception as e:
            logger.debug("semantic_cache_set_failed", error=str(e))

    # ── 对话 ──────────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[ChatMessage],
        model_config_id: int | None,
        db: AsyncSession,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        call_type: str = "chat",
        use_cache: bool = True,
        cache_ttl: int = _SEMANTIC_CACHE_TTL_DEFAULT,
    ) -> ChatResult:
        """
        非流式对话，自动写入调用日志。
        - model_config_id=None 时使用系统默认模型
        - 带三状态熔断器：主力模型 OPEN 时自动切换备用模型
        - 带语义缓存：相同 messages 命中缓存时跳过 LLM 调用（use_cache=False 可关闭）
        """
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db)
            model_config_id = config.id

        eff_temperature = temperature if temperature is not None else settings.AI_DEFAULT_TEMPERATURE
        eff_max_tokens = max_tokens or config.max_tokens

        # ── 语义缓存检查（仅 temperature 为 0 或 use_cache=True 时）──────────
        cache_key = self._make_cache_key(model_config_id, messages)
        if use_cache and eff_temperature == 0:
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.info("semantic_cache_hit", model_config_id=model_config_id)
                await self._write_call_log(
                    db=db, call_type=call_type, model_config_id=model_config_id,
                    user_id=user_id, conversation_id=conversation_id,
                    result=cached, latency_ms=0, status="cached", error_msg=None,
                )
                return cached

        # ── 熔断器检查 ────────────────────────────────────────────────────────
        circuit_state = await self._get_circuit_state(model_config_id)
        if circuit_state == CircuitState.OPEN:
            # 主力模型熔断，尝试切换备用模型
            fallback = await self._get_fallback_config(db, model_config_id)
            if fallback:
                logger.warning(
                    "circuit_breaker_fallback",
                    primary_model_id=model_config_id,
                    fallback_model_id=fallback.id,
                )
                provider = self._build_provider(fallback)
                config = fallback
                model_config_id = fallback.id
            else:
                # 无备用模型，返回友好错误
                raise RuntimeError(
                    f"模型 [{config.name}] 当前不可用（熔断中），请稍后重试"
                )

        start_ms = int(time.time() * 1000)
        status = "success"
        error_msg = None
        result: ChatResult | None = None

        try:
            result = await provider.chat(
                messages=messages,
                model=config.model_id,
                temperature=eff_temperature,
                max_tokens=eff_max_tokens,
            )
            # 调用成功，重置熔断器
            await self._on_call_success(model_config_id)

            # 写入语义缓存（仅 temperature=0 时缓存，有随机性的结果不缓存）
            if use_cache and eff_temperature == 0 and result:
                await self._set_to_cache(cache_key, result, cache_ttl)

        except Exception as e:
            status = "error"
            error_msg = str(e)
            # 记录失败，可能触发熔断
            await self._on_call_failure(model_config_id)
            raise
        finally:
            latency_ms = int(time.time() * 1000) - start_ms
            await self._write_call_log(
                db=db,
                call_type=call_type,
                model_config_id=model_config_id,
                user_id=user_id,
                conversation_id=conversation_id,
                result=result,
                latency_ms=latency_ms,
                status=status,
                error_msg=error_msg,
            )

        return result  # type: ignore[return-value]

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model_config_id: int | None,
        db: AsyncSession,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话，yield 每个文本 chunk"""
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db)

        eff_temperature = temperature if temperature is not None else settings.AI_DEFAULT_TEMPERATURE
        eff_max_tokens = max_tokens or config.max_tokens

        async for chunk in provider.stream_chat(
            messages=messages,
            model=config.model_id,
            temperature=eff_temperature,
            max_tokens=eff_max_tokens,
        ):
            yield chunk

    # ── 向量化 ────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_embed_cache_key(model_config_id: int, text: str) -> str:
        """生成 embedding 缓存 key"""
        digest = hashlib.sha256(f"{model_config_id}:{text}".encode()).hexdigest()
        return f"llm:embed_cache:{digest}"

    @classmethod
    async def _get_embed_from_cache(cls, cache_keys: list[str]) -> dict[str, list[float]]:
        """批量从 Redis 缓存中获取 embedding"""
        try:
            redis = await _get_redis()
            if cache_keys:
                result = await redis.mget(cache_keys)
                return {cache_keys[i]: json.loads(result[i]) for i in range(len(cache_keys)) if result[i]}
        except Exception as e:
            logger.debug("embed_cache_get_failed", error=str(e))
        return {}

    @classmethod
    async def _set_embed_to_cache(cls, items: list[tuple[str, list[float]]], ttl: int = 86400) -> None:
        """批量写入 embedding 缓存（默认 24 小时）"""
        try:
            redis = await _get_redis()
            pipe = redis.pipeline()
            for key, value in items:
                pipe.set(key, json.dumps(value), ex=ttl)
            await pipe.execute()
        except Exception as e:
            logger.debug("embed_cache_set_failed", error=str(e))

    async def embed(
        self,
        texts: list[str],
        model_config_id: int | None,
        db: AsyncSession,
        use_cache: bool = True,
    ) -> list[list[float]]:
        """
        文本向量化，model_config_id=None 时使用默认嵌入模型。
        支持 Redis 缓存，相同文本不会重复向量化。
        """
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db, embed=True)
            model_config_id = config.id

        results: list[list[float] | None] = [None] * len(texts)

        if use_cache:
            cache_keys = [self._make_embed_cache_key(model_config_id, text) for text in texts]
            cached = await self._get_embed_from_cache(cache_keys)

            for i, key in enumerate(cache_keys):
                if key in cached:
                    results[i] = cached[key]

        need_embed = [(i, texts[i]) for i in range(len(texts)) if results[i] is None]

        if need_embed:
            need_texts = [t for _, t in need_embed]
            embeddings = await provider.embed(need_texts, config.model_id)

            for idx, (orig_idx, text) in enumerate(need_embed):
                results[orig_idx] = embeddings[idx]

            if use_cache:
                cache_items = [
                    (self._make_embed_cache_key(model_config_id, text), embeddings[idx])
                    for idx, (orig_idx, text) in enumerate(need_embed)
                ]
                await self._set_embed_to_cache(cache_items)

        return [r for r in results if r is not None]

    # ── 调用日志 ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _write_call_log(
        db: AsyncSession,
        call_type: str,
        model_config_id: int,
        user_id: int | None,
        conversation_id: int | None,
        result: ChatResult | None,
        latency_ms: int,
        status: str,
        error_msg: str | None,
    ) -> None:
        """非阻塞写入 AI 调用日志（Fire-and-forget）"""
        try:
            from app.ai.conversation.models import AiCallLog

            log = AiCallLog(
                call_type=call_type,
                model_config_id=model_config_id,
                user_id=user_id,
                conversation_id=conversation_id,
                request_tokens=result.prompt_tokens if result else 0,
                response_tokens=result.completion_tokens if result else 0,
                total_tokens=result.total_tokens if result else 0,
                latency_ms=latency_ms,
                status=status,
                error_msg=error_msg,
            )
            db.add(log)
            await db.flush()
        except Exception as e:
            logger.warning("ai_call_log_write_failed", error=str(e))
