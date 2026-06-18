"""
若茗 PaaS - LLM 网关服务层
职责：
  1. 根据 AiModelConfig 实例化并缓存 Provider（进程内缓存 + Redis Pub/Sub 多 Worker 失效）
  2. 统一对话入口，自动记录调用日志（ai_call_log）
  3. 向量化代理
Author: ruoming
"""
from __future__ import annotations

import asyncio
import time
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
        """根据配置构建 Provider 实例"""
        raw_key = decrypt_value(config.api_key) if config.api_key else ""
        match config.provider:
            case "zhuilu":
                return ZhuiluProvider(
                    api_key=raw_key,
                    base_url=config.base_url or settings.ZHUILU_BASE_URL,
                )
            case "openai":
                return OpenAICompatProvider(
                    api_key=raw_key,
                    base_url=config.base_url or settings.OPENAI_BASE_URL,
                    provider_name="openai",
                )
            case "ollama":
                return OpenAICompatProvider(
                    api_key="",
                    base_url=config.base_url or settings.OLLAMA_BASE_URL,
                    provider_name="ollama",
                )
            case "azure":
                return OpenAICompatProvider(
                    api_key=raw_key,
                    base_url=config.base_url or "",
                    provider_name="azure",
                )
            case _:
                raise ValueError(f"不支持的模型提供商：{config.provider}")

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
    ) -> ChatResult:
        """
        非流式对话，自动写入调用日志。
        model_config_id=None 时使用系统默认模型。
        """
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db)
            model_config_id = config.id

        eff_temperature = temperature if temperature is not None else settings.AI_DEFAULT_TEMPERATURE
        eff_max_tokens = max_tokens or config.max_tokens

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
        except Exception as e:
            status = "error"
            error_msg = str(e)
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
        """流式对话，返回 AsyncGenerator[str, None]"""
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db)

        eff_temperature = temperature if temperature is not None else settings.AI_DEFAULT_TEMPERATURE
        eff_max_tokens = max_tokens or config.max_tokens

        return provider.stream_chat(
            messages=messages,
            model=config.model_id,
            temperature=eff_temperature,
            max_tokens=eff_max_tokens,
        )

    # ── 向量化 ────────────────────────────────────────────────────────────────

    async def embed(
        self,
        texts: list[str],
        model_config_id: int | None,
        db: AsyncSession,
    ) -> list[list[float]]:
        """文本向量化，model_config_id=None 时使用默认嵌入模型"""
        if model_config_id:
            config = await self._load_config(model_config_id, db)
            provider = await self.get_provider(model_config_id, db)
        else:
            provider, config = await self.get_default_provider(db, embed=True)

        return await provider.embed(texts, config.model_id)

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
