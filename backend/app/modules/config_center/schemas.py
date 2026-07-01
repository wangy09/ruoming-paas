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
    category: str | None = Field(None, description="配置分类")
    config_type: str = Field("input", description="表单控件类型")
    default_value: str | None = None
    options: list[dict[str, Any]] | dict[str, Any] | None = None
    required: bool = False
    regex: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    sort: int = 0
    status: int = 1
    label: str | None = None
    description: str | None = None
    is_public: bool = False
    app_key: str | None = None
    user_id: int | None = None


class ConfigUpdate(BaseModel):
    """更新配置项"""
    config_val: str | None = None
    val_type: str | None = None
    is_encrypted: bool | None = None
    category: str | None = None
    config_type: str | None = None
    default_value: str | None = None
    options: list[dict[str, Any]] | dict[str, Any] | None = None
    required: bool | None = None
    regex: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    sort: int | None = None
    status: int | None = None
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
    display_val: str | None = None
    val_type: str
    is_encrypted: bool
    category: str | None = None
    config_type: str
    default_value: str | None = None
    options: list[dict[str, Any]] | dict[str, Any] | None = None
    required: bool
    regex: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    sort: int
    status: int
    label: str | None
    description: str | None
    is_public: bool
    app_key: str | None
    user_id: int | None
    tenant_id: int | None


class PublicConfigOut(BaseModel):
    """前端公开配置输出"""

    config_key: str
    config_val: str | None
    val_type: str
    category: str | None = None
    label: str | None = None


class ConfigExportOut(BaseModel):
    """配置导出输出"""

    version: str = "1.0"
    items: list[ConfigOut]


class ConfigImportIn(BaseModel):
    """配置导入输入"""

    items: list[ConfigCreate]
    overwrite: bool = Field(False, description="已存在配置是否覆盖")


class ConfigImportResult(BaseModel):
    """配置导入结果"""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ConfigCacheClearResult(BaseModel):
    """配置缓存清理结果"""

    cleared: int


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
    changed_by_name: str | None = None
    changed_at: Any
    remark: str | None


class MergedConfigQuery(BaseModel):
    """合并查询请求"""
    keys: list[str] = Field(..., description="要查询的配置键列表")
    app_key: str | None = None
