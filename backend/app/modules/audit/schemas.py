"""
若茗 PaaS - 审计日志 Schemas
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int | None
    user_id: int | None
    username: str | None
    module: str | None
    action: str | None
    resource_type: str | None
    resource_id: str | None
    event_type: str | None
    status: int
    error_msg: str | None
    created_at: datetime

    # 前端需要的扩展字段
    before_data: dict | None = None
    after_data: dict | None = None
    detail: dict | None = None
    request_body: dict | list | str | int | bool | None = None
    response_body: dict | list | str | int | bool | None = None
    status_code: int | None = None
    request_ip: str | None = None
    user_agent: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None
    trace_id: str | None = None
    path: str | None = None
    method: str | None = None


class LoginLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int | None
    user_id: int | None
    username: str | None
    login_type: str | None
    status: int
    fail_reason: str | None
    login_ip: str | None
    user_agent: str | None
    created_at: datetime

    # 前端需要的扩展字段
    ip_address: str | None = None
