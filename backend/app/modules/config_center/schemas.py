"""
若茗 PaaS - 配置中心 Pydantic Schema
Author: ruoming
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigCreate(BaseModel):
    """创建配置项"""
    scope: str = Field(..., description="层级：global/tenant/app/user")
    config_key: str = Field(..., description="配置键，如 ai.cache.enabled")
    config_val: str | None = Field(None, description="配置值")
    val_type: str = Field("string", description="值类型：string/int/bool/json")
    is_encrypted: bool = Field(False, description="是否加密存储")
    label: str | None = None
    description: str | None = None
    is_public: bool = False
    app_key: str | None = None
    user_id: int | None = None


class ConfigUpdate(BaseModel):
    """更新配置项"""
    config_val: str | None = None
    label: str | None = None
    description: str | None = None
    is_public: bool | None = None
    remark: str | None = None


class ConfigOut(BaseModel):
    """配置项输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    config_key: str
    config_val: str | None
    val_type: str
    is_encrypted: bool
    label: str | None
    description: str | None
    is_public: bool
    app_key: str | None
    user_id: int | None
    tenant_id: int | None


class ConfigHistoryOut(BaseModel):
    """配置变更历史输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_key: str
    scope_type: str
    scope_id: int | None
    old_value: str | None
    new_value: str | None
    changed_by: int | None
    changed_at: Any
    remark: str | None


class MergedConfigQuery(BaseModel):
    """合并查询请求"""
    keys: list[str] = Field(..., description="要查询的配置键列表")
    app_key: str | None = None
