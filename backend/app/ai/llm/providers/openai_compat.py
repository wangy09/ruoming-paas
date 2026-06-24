"""
若茗 PaaS - OpenAI 兼容 Provider（含 Ollama 本地模型）
任何遵守 OpenAI REST API 协议的服务（OpenAI、Azure OpenAI、Ollama、LocalAI 等）
均可通过此 Provider 接入，只需传入不同 base_url 和 api_key 即可。
Author: ruoming
"""
import json
from typing import AsyncGenerator

import httpx
import structlog

from app.ai.llm.providers.base import BaseLLMProvider, ChatMessage, ChatResult, ModelInfo

logger = structlog.get_logger(__name__)


class OpenAICompatProvider(BaseLLMProvider):
    """
    OpenAI 兼容 Provider。
    支持 OpenAI 官方 API、Azure OpenAI、Ollama（本地）、LocalAI 等。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        provider_name: str = "openai",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

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
            resp = await self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "openai_chat_error",
                provider=self.provider_name,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            raise

        data = resp.json()
        # 兼容阿里云 MaaS 非标准格式：{"finish_reason": "stop", "text": "..."}
        if "choices" not in data and "text" in data:
            return ChatResult(
                content=data["text"] or "",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                model=model,
                finish_reason=data.get("finish_reason", "stop"),
            )
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ChatResult(
            content=choice["message"]["content"] or "",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model=data.get("model", model),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True, **kwargs)
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                # 标准 SSE 格式：data: {...}
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                        # 阿里云 MaaS 非标准格式：{"text": "...", "finish_reason": "..."}
                        if "choices" not in chunk and "text" in chunk:
                            yield chunk["text"]
                        else:
                            delta = chunk["choices"][0].get("delta", {})
                            if content := delta.get("content"):
                                yield content
                    except (json.JSONDecodeError, KeyError):
                        continue
                else:
                    # 非 SSE 格式：直接裸 JSON（阿里云 MaaS 兼容模式）
                    try:
                        chunk = json.loads(line)
                        if "text" in chunk:
                            yield chunk["text"]
                        elif "choices" in chunk:
                            delta = chunk["choices"][0].get("delta", {})
                            if content := delta.get("content"):
                                yield content
                    except (json.JSONDecodeError, KeyError):
                        continue

    # ── 向量化 ────────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        resp = await self._client.post(
            "/embeddings",
            json={"model": model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    # ── 模型列表 ──────────────────────────────────────────────────────────────

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            data = resp.json()
            return [
                ModelInfo(
                    id=m["id"],
                    name=m.get("name", m["id"]),
                    context_length=m.get("context_length", 4096),
                    supports_streaming=True,
                )
                for m in data.get("data", [])
            ]
        except Exception as e:
            logger.warning("openai_list_models_failed", provider=self.provider_name, error=str(e))
            return []

    async def test_connection(self) -> bool:
        """Ollama 兼容：先尝试 /models（Ollama），再尝试 OpenAI 的 /models"""
        for path in ["/models", "/models"]:
            try:
                resp = await self._client.get(path, timeout=10.0)
                if resp.status_code < 400:
                    return True
            except Exception:
                pass
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
        payload: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update({k: v for k, v in kwargs.items() if k not in payload})
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()
