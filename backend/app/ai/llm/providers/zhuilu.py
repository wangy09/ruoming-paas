"""
若茗 PaaS - 追鹿大模型 Provider（OpenAI 兼容协议）
追鹿使用 OpenAI 兼容的 /v1/chat/completions 接口，故此处直接复用 openai 客户端逻辑。
Author: ruoming
"""
import json
from typing import AsyncGenerator

import httpx
import structlog

from app.ai.llm.providers.base import BaseLLMProvider, ChatMessage, ChatResult, ModelInfo

logger = structlog.get_logger(__name__)

# 追鹿支持的嵌入维度（按模型不同）
_EMBED_DIMENSION_MAP: dict[str, int] = {
    "text-embedding-v1": 1536,
    "text-embedding-v2": 1024,
}


class ZhuiluProvider(BaseLLMProvider):
    """
    追鹿大模型 Provider。
    使用 OpenAI 兼容协议（/v1/chat/completions, /v1/embeddings, /v1/models）。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.zhuilu.ai/v1",
        timeout: float = 120.0,
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
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
            logger.error("zhuilu_chat_error", status=e.response.status_code, body=e.response.text)
            raise

        data = resp.json()
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
        self.last_stream_usage = {}  # 重置上次 usage
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True, **kwargs)
        payload.setdefault("stream_options", {"include_usage": True})
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                    if "usage" in chunk and chunk["usage"]:
                        self.last_stream_usage = chunk["usage"]
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
        # 保持顺序
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    # ── 重排序 ────────────────────────────────────────────────────────────────

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        调用 Rerank API 对文档重排序（Cross-Encoder）。
        自动适配不同厂商的端点路径和响应格式。
        """
        if not documents:
            return []

        payload: dict = {
            "model": model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        last_error: Exception | None = None
        for endpoint in ["/rerank", "/reranks"]:
            try:
                resp = await self._client.post(endpoint, json=payload)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results")
                if results is None and isinstance(data.get("output"), dict):
                    results = data["output"].get("results", [])

                if not results:
                    return []

                return [
                    (int(item["index"]), float(item["relevance_score"]))
                    for item in results
                ]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    continue
                raise
            except Exception as e:
                last_error = e
                continue

        raise NotImplementedError(
            f"Rerank API 不可用（已尝试 /rerank 和 /reranks 端点）。"
            f"请检查 base_url 配置是否正确。最后错误: {last_error}"
        )

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
            logger.warning("zhuilu_list_models_failed", error=str(e))
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
