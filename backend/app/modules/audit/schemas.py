"""
若茗 PaaS - 审计日志 Schemas
"""
from datetime import datetime

from pydantic import BaseModel


class AuditLogListResponse(BaseModel):
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


class LoginLogListResponse(BaseModel):
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
