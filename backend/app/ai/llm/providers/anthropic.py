"""
若茗 PaaS - Anthropic Claude 原生 Provider
使用 Anthropic Messages API（/v1/messages），支持 Claude 3.5 / 3.7 / 4 系列模型。
Author: ruoming
"""
import json
from typing import AsyncGenerator

import httpx
import structlog

from app.ai.llm.providers.base import BaseLLMProvider, ChatMessage, ChatResult, ModelInfo

logger = structlog.get_logger(__name__)

# Anthropic API 常量
_ANTHROPIC_API_BASE = "https://api.anthropic.com/v1"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude 原生 Provider。
    使用 Messages API（/v1/messages），支持非流式、流式对话和模型列表。
    Anthropic 不提供 Embedding API，embed() 将抛出 NotImplementedError。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = _ANTHROPIC_API_BASE,
        timeout: float = 120.0,
        provider_name: str = "anthropic",
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if api_key:
            headers["x-api-key"] = api_key

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    # ── 对话 ──────────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ChatResult:
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=False, **kwargs)
        try:
            resp = await self._client.post("/messages", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "anthropic_chat_error",
                provider=self.provider_name,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            raise

        data = resp.json()
        # content 是数组，取 text 类型的块拼接
        content_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        usage = data.get("usage", {})
        return ChatResult(
            content="".join(content_parts),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            model=data.get("model", model),
            finish_reason=_map_stop_reason(data.get("stop_reason")),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        self.last_stream_usage = {}
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True, **kwargs)

        async with self._client.stream("POST", "/messages", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:]
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")
                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
                elif event_type == "message_delta":
                    # 流式结束时的 usage（output_tokens）
                    usage = event.get("usage", {})
                    if usage:
                        self.last_stream_usage = {
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
                            "total_tokens": (
                                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                            ),
                        }
                elif event_type == "message_stop":
                    break

    # ── 向量化 ────────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        raise NotImplementedError("Anthropic 不提供 Embedding API，请使用其他厂商的向量化模型")

    # ── 模型列表 ──────────────────────────────────────────────────────────────

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            data = resp.json()
            return [
                ModelInfo(
                    id=m["id"],
                    name=m.get("display_name", m["id"]),
                    context_length=m.get("context_window", 8192),
                    supports_streaming=True,
                )
                for m in data.get("data", [])
            ]
        except Exception as e:
            logger.warning("anthropic_list_models_failed", provider=self.provider_name, error=str(e))
            return []

    async def test_connection(self) -> bool:
        try:
            resp = await self._client.get("/models", timeout=10.0)
            return resp.status_code < 400
        except Exception:
            return False

    # ── 私有工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_payload(
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
        **kwargs,
    ) -> dict:
        # Anthropic 的 system 消息需单独提取，不放入 messages 数组
        system_parts: list[str] = []
        chat_messages: list[dict] = []
        for m in messages:
            if m.role == "system":
                if m.content:
                    system_parts.append(m.content)
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        payload: dict = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        payload.update({k: v for k, v in kwargs.items() if k not in payload})
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()


def _map_stop_reason(reason: str | None) -> str:
    """将 Anthropic 的 stop_reason 映射为统一格式"""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    return mapping.get(reason or "", "stop")
