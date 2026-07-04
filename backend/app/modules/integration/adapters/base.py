"""
第三方协作平台适配器协议。
业务侧只依赖 CollaborationAdapter，不直接依赖飞书/钉钉/企微 SDK。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterContext:
    provider: str
    config: dict[str, Any] = field(default_factory=dict)
    secret_config: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResult:
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    external_message_id: str | None = None


class CollaborationAdapter(ABC):
    provider: str
    name: str
    capabilities: list[str]
    required_secret_fields: list[str]
    optional_secret_fields: list[str] = []
    config_fields: list[str] = []

    @abstractmethod
    async def test(self, ctx: AdapterContext) -> AdapterResult:
        """测试连接是否可用。"""

    @abstractmethod
    async def send_message(
        self,
        ctx: AdapterContext,
        *,
        message_type: str,
        title: str | None,
        content: str,
        target: dict[str, Any],
        metadata: dict[str, Any],
    ) -> AdapterResult:
        """发送统一消息。"""
