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


@dataclass(frozen=True)
class ContactDepartment:
    external_id: str
    name: str
    parent_external_id: str | None = None
    sort: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactUser:
    external_id: str
    name: str
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    department_external_ids: list[str] = field(default_factory=list)
    active: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactSyncData:
    departments: list[ContactDepartment] = field(default_factory=list)
    users: list[ContactUser] = field(default_factory=list)


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

    async def fetch_contacts(self, ctx: AdapterContext) -> ContactSyncData:
        """拉取通讯录。仅 contact_sync 能力适配器需要实现。"""
        _ = ctx
        raise NotImplementedError("当前平台未实现通讯录同步")
