"""
若茗 PaaS - 租户管理 Schemas
Author: ruoming
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    """创建租户"""

    name: str = Field(..., max_length=64, description="租户名称")
    code: str = Field(..., max_length=64, description="租户唯一标识（域名前缀）")
    plan: str = Field(default="basic", description="套餐：trial/basic/pro/enterprise")
    contact_email: str | None = Field(default=None, max_length=128, description="联系邮箱")
    contact_phone: str | None = Field(default=None, max_length=20, description="联系电话")
    remark: str | None = Field(default=None, description="备注")
    admin_username: str = Field(..., max_length=64, description="租户管理员用户名")
    admin_password: str = Field(..., min_length=8, max_length=128, description="租户管理员密码")
    admin_email: str | None = Field(default=None, max_length=128, description="租户管理员邮箱")


class TenantUpdate(BaseModel):
    """更新租户"""

    name: str | None = Field(default=None, max_length=64, description="租户名称")
    domain: str | None = Field(default=None, max_length=128, description="自定义域名")
    logo: str | None = Field(default=None, max_length=256, description="租户 Logo URL")
    plan: str | None = Field(default=None, description="套餐")
    status: int | None = Field(default=None, description="状态：1正常 2试用 3过期 0禁用")
    contact_email: str | None = Field(default=None, max_length=128, description="联系邮箱")
    contact_phone: str | None = Field(default=None, max_length=20, description="联系电话")
    remark: str | None = Field(default=None, description="备注")


class TenantQuotaUpdate(BaseModel):
    """更新租户配额"""

    max_users: int | None = Field(default=None, ge=1, description="最大用户数")
    max_storage_gb: float | None = Field(default=None, ge=0, description="存储配额(GB)")
    max_api_calls_day: int | None = Field(default=None, ge=0, description="每日 API 调用次数上限")
    max_ai_tokens_day: int | None = Field(default=None, ge=0, description="每日 AI Token 消耗上限")
    max_concurrent: int | None = Field(default=None, ge=1, description="最大并发 AI 请求数")


class TenantListItem(BaseModel):
    """租户列表项"""

    id: int
    name: str
    code: str
    domain: str | None
    plan: str
    status: int
    expire_at: datetime | None
    trial_end_at: datetime | None
    max_users: int
    max_api_calls_day: int
    contact_email: str | None
    contact_phone: str | None
    registered_by: int | None
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantInfo(TenantListItem):
    """租户详情"""

    logo: str | None
    max_storage_gb: float
    max_ai_tokens_day: int
    max_concurrent: int
    config: dict[str, Any]
    remark: str | None


class TenantUsage(BaseModel):
    """租户用量统计"""

    tenant_id: int
    tenant_name: str
    stat_date: str
    api_calls: int
    ai_tokens: int
    storage_bytes: int


class TenantApprove(BaseModel):
    """租户审核"""

    status: int = Field(..., description="审核状态：1通过 0拒绝")
    remark: str | None = Field(default=None, description="审核备注")