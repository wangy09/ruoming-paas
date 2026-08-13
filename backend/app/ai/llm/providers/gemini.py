"""
若茗 PaaS - Google Gemini 原生 Provider
使用 Generative Language API（/v1beta/models/{model}:generateContent），
支持 Gemini 1.5 / 2.0 / 2.5 系列模型。
Author: ruoming
"""
import json
from typing import AsyncGenerator

import httpx
import structlog

from app.ai.llm.providers.base import BaseLLMProvider, ChatMessage, ChatResult, ModelInfo

logger = structlog.get_logger(__name__)

# Gemini API 常量
_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini 原生 Provider。
    使用 GenerateContent API，支持非流式、流式对话、向量化和模型列表。
    API Key 通过 query parameter（?key=）传递。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = _GEMINI_API_BASE,
        timeout: float = 120.0,
        provider_name: str = "gemini",
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
            params={"key": api_key} if api_key else None,
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
        payload = self._build_payload(messages, temperature, max_tokens, **kwargs)
        endpoint = f"/models/{model}:generateContent"
        try:
            resp = await self._client.post(endpoint, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "gemini_chat_error",
                provider=self.provider_name,
                model=model,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            raise

        data = resp.json()
        candidates = data.get("candidates", [])
        content = ""
        finish_reason = "stop"
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts if "text" in p)
            finish_reason = _map_finish_reason(candidates[0].get("finishReason"))

        usage = data.get("usageMetadata", {})
        return ChatResult(
            content=content,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
            model=model,
            finish_reason=finish_reason,
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
        payload = self._build_payload(messages, temperature, max_tokens, **kwargs)
        endpoint = f"/models/{model}:streamGenerateContent"

        async with self._client.stream("POST", endpoint, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                # Gemini 流式返回 JSON 数组元素，每行一个 JSON 对象（非 SSE 格式）
                # 也可能以 "data: " 前缀返回（alt=sse 模式），两种都兼容
                raw = line
                if line.startswith("data: "):
                    raw = line[6:]
                if raw.strip() == "[" or raw.strip() == "]":
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # 提取文本
                candidates = chunk.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if text := part.get("text"):
                            yield text

                # 提取 usage（通常在最后一个 chunk）
                usage = chunk.get("usageMetadata")
                if usage:
                    self.last_stream_usage = {
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                        "total_tokens": usage.get("totalTokenCount", 0),
                    }

    # ── 向量化 ────────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """使用 Gemini embedContent API 批量向量化"""
        results: list[list[float]] = []
        for text in texts:
            resp = await self._client.post(
                f"/models/{model}:embedContent",
                json={
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": text}]},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results.append(data.get("embedding", {}).get("values", []))
        return results

    # ── 模型列表 ──────────────────────────────────────────────────────────────

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                # 只返回生成式模型（跳过 embed 等）
                supported = m.get("supportedGenerationMethods", [])
                if "generateContent" not in supported:
                    continue
                model_id = m.get("name", "").removeprefix("models/")
                models.append(ModelInfo(
                    id=model_id,
                    name=m.get("displayName", model_id),
                    context_length=m.get("inputTokenLimit", 8192),
                    supports_streaming="streamGenerateContent" in supported,
                ))
            return models
        except Exception as e:
            logger.warning("gemini_list_models_failed", provider=self.provider_name, error=str(e))
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
        temperature: float,
        max_tokens: int | None,
        **kwargs,
    ) -> dict:
        # Gemini 的 system 消息单独放在 systemInstruction
        system_parts: list[str] = []
        contents: list[dict] = []
        for m in messages:
            if m.role == "system":
                if m.content:
                    system_parts.append(m.content)
            else:
                # Gemini 用 "model" 而非 "assistant"
                role = "model" if m.role == "assistant" else m.role
                contents.append({
                    "role": role,
                    "parts": [{"text": m.content}],
                })

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }
        # 合并额外参数到 generationConfig
        gen_config = payload["generationConfig"]
        gen_config.update({k: v for k, v in kwargs.items() if k not in gen_config})
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()


def _map_finish_reason(reason: str | None) -> str:
    """将 Gemini 的 finishReason 映射为统一格式"""
    mapping = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
    }
    return mapping.get(reason or "", "stop")
