"""
若茗 PaaS - 第三方协作平台集成 Schema
"""
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProviderCode = Literal["feishu", "dingtalk", "wecom", "custom"]
CapabilityCode = Literal["bot_message", "oauth", "contact_sync", "event_callback"]
FieldUpdateMode = Literal["never", "if_empty", "always"]


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


class ContactSyncStrategy(BaseModel):
    sync_departments: bool = True
    sync_users: bool = True
    sync_avatar: bool = True
    disable_missing_users: bool = False
    username_strategy: list[Literal["email_prefix", "phone", "name", "external_id"]] = Field(
        default_factory=lambda: cast(
            list[Literal["email_prefix", "phone", "name", "external_id"]],
            ["email_prefix", "phone", "name", "external_id"],
        ),
        description="新建用户时用户名生成优先级",
    )
    nickname_strategy: list[Literal["name", "nickname", "username"]] = Field(
        default_factory=lambda: cast(list[Literal["name", "nickname", "username"]], ["name", "nickname"]),
        description="用户昵称更新优先级",
    )
    overwrite_email: bool = True
    overwrite_phone: bool = False
    overwrite_department: bool = True
    email_update_mode: FieldUpdateMode = Field(default="always", description="邮箱更新策略")
    phone_update_mode: FieldUpdateMode = Field(default="never", description="手机号更新策略")
    department_update_mode: FieldUpdateMode = Field(default="always", description="部门归属更新策略")

    @model_validator(mode="before")
    @classmethod
    def _fill_update_modes_from_legacy_overwrite(cls, data):
        if not isinstance(data, dict):
            return data
        legacy_map = {
            "email_update_mode": "overwrite_email",
            "phone_update_mode": "overwrite_phone",
            "department_update_mode": "overwrite_department",
        }
        for mode_field, legacy_field in legacy_map.items():
            if mode_field not in data and isinstance(data.get(legacy_field), bool):
                data[mode_field] = "always" if data[legacy_field] else "never"
        return data

    @model_validator(mode="after")
    def _sync_legacy_overwrite_fields(self):
        self.overwrite_email = self.email_update_mode == "always"
        self.overwrite_phone = self.phone_update_mode == "always"
        self.overwrite_department = self.department_update_mode == "always"
        return self


class ContactSyncRequest(ContactSyncStrategy):
    provider: Literal["feishu", "dingtalk", "wecom"] = Field(description="同步来源")
    connection_id: int | None = Field(default=None, description="指定连接；为空时使用默认连接")


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


class ContactSyncPreviewItem(BaseModel):
    action: str
    target_type: str
    external_id: str | None = None
    local_id: int | None = None
    name: str | None = None
    reason: str | None = None


class ContactSyncPreviewResult(ContactSyncResult):
    details: list[ContactSyncPreviewItem] = Field(default_factory=list)


class ContactSyncCheckItem(BaseModel):
    key: str
    name: str
    status: Literal["success", "warning", "failed"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ContactSyncCheckResult(BaseModel):
    provider: str
    connection_id: int | None = None
    status: Literal["success", "warning", "failed"]
    summary: str
    departments_count: int = 0
    users_count: int = 0
    avatar_users_count: int = 0
    missing_users_count: int = 0
    checks: list[ContactSyncCheckItem] = Field(default_factory=list)


class ContactSyncLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    provider: str
    connection_id: int
    operation: str
    status: str
    operator_id: int | None = None
    request_data: dict | None = None
    result_data: dict | None = None
    detail_data: dict | None = None
