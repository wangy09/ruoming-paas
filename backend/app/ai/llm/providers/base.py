"""
若茗 PaaS - LLM Provider 抽象基类
所有模型提供商实现此接口，业务层只依赖此抽象，不感知具体 Provider。
Author: ruoming
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator


@dataclass
class ModelInfo:
    """模型基本信息"""
    id: str
    name: str
    context_length: int = 4096
    supports_streaming: bool = True
    supports_embedding: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class ChatMessage:
    """对话消息"""
    role: str   # user / assistant / system / tool
    content: str
    tool_calls: list | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


@dataclass
class ChatResult:
    """对话结果（非流式）"""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    finish_reason: str = "stop"


class BaseLLMProvider(ABC):
    """
    所有 LLM 模型提供商的抽象基类。
    - chat()：非流式返回 ChatResult
    - stream_chat()：流式返回 AsyncGenerator[str, None]
    - embed()：返回向量列表
    - list_models()：列出可用模型
    """

    def __init__(self) -> None:
        # 最近一次流式对话的 token usage（由 stream_chat 填充）
        self.last_stream_usage: dict = {}

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ChatResult:
        """非流式对话推理"""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式对话推理，逐 token yield 内容片段"""
        ...

    @abstractmethod
    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """文本向量化，返回 [[float, ...], ...]"""
        ...

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        使用 Rerank 模型对文档重排序（Cross-Encoder）。
        子类应调用厂商 Rerank API（如 Cohere / Jina / SiliconFlow 的 /rerank 端点）。

        Args:
            query: 查询文本
            documents: 候选文档文本列表
            model: Rerank 模型 ID
            top_n: 返回前 N 条结果，None 表示返回全部

        Returns:
            [(文档在原列表中的索引, 相关性分数), ...] 按相关性降序排列

        Raises:
            NotImplementedError: Provider 不支持 Rerank API
        """
        raise NotImplementedError(f"{self.__class__.__name__} 不支持 Rerank")

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """列出提供商支持的所有模型"""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """测试 API 连通性"""
        ...
