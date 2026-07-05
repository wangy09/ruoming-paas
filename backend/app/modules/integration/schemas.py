"""
若茗 PaaS - 第三方协作平台集成 Schema
"""
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProviderCode = Literal["feishu", "dingtalk", "wecom", "custom"]
CapabilityCode = Literal["bot_message", "oauth", "contact_sync", "event_callback"]


class ProviderInfo(BaseModel):
    code: ProviderCode
    name: str
    capabilities: list[CapabilityCode]
    required_secret_fields: list[str]
    optional_secret_fields: list[str] = Field(default_factory=list)
    config_fields: list[str] = Field(default_factory=list)


class IntegrationConnectionCreate(BaseModel):
    provider: ProviderCode
    name: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    is_default: bool = False
    capabilities: list[CapabilityCode] = Field(
        default_factory=lambda: cast(list[CapabilityCode], ["bot_message"])
    )
    config: dict[str, Any] = Field(default_factory=dict)
    secret_config: dict[str, str] = Field(default_factory=dict)
    sort: int = 0

    @field_validator("secret_config")
    @classmethod
    def validate_secret_values(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if item is not None and not isinstance(item, str):
                raise ValueError(f"{key} 必须是字符串")
        return value


class IntegrationConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    enabled: bool | None = None
    is_default: bool | None = None
    capabilities: list[CapabilityCode] | None = None
    config: dict[str, Any] | None = None
    secret_config: dict[str, str] | None = None
    sort: int | None = None


class IntegrationConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    provider_name: str
    name: str
    enabled: bool
    is_default: bool
    capabilities: list[str]
    config: dict[str, Any]
    secret_configured: bool
    status: int
    last_test_status: str | None = None
    last_test_message: str | None = None
    sort: int
    tenant_id: int | None = None


class IntegrationTestResult(BaseModel):
    success: bool
    provider: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class IntegrationSendMessageRequest(BaseModel):
    connection_id: int | None = Field(default=None, description="指定连接；为空时使用当前租户默认连接")
    provider: ProviderCode | None = Field(default=None, description="按平台选择默认连接")
    message_type: Literal["text", "markdown"] = "text"
    title: str | None = Field(default=None, max_length=128)
    content: str = Field(min_length=1, max_length=8000)
    target: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationSendMessageResult(BaseModel):
    success: bool
    provider: str
    connection_id: int
    message: str
    external_message_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ContactSyncRequest(BaseModel):
    provider: Literal["feishu", "dingtalk", "wecom"] = Field(description="同步来源")
    connection_id: int | None = Field(default=None, description="指定连接；为空时使用默认连接")
    sync_departments: bool = True
    sync_users: bool = True
    sync_avatar: bool = True
    disable_missing_users: bool = False


class ContactSyncResult(BaseModel):
    provider: str
    connection_id: int
    departments_created: int = 0
    departments_updated: int = 0
    users_created: int = 0
    users_updated: int = 0
    users_disabled: int = 0
    skipped_users: int = 0
    errors: list[str] = Field(default_factory=list)
