"""
若茗 PaaS - 权限模块 Pydantic 模型
Author: ruoming
"""
from typing import Literal

from pydantic import BaseModel, Field

DashboardTemplate = Literal["platform", "tenant", "developer", "personal"]


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_:]+$")
    description: str | None = None
    parent_id: int = Field(default=0, description="父角色 ID（0=无父角色）")
    data_scope: int = Field(default=1, ge=1, le=5, description="数据范围：1全部 2自定义 3本部门 4本部门及子部门 5仅本人")
    data_scope_depts: list[int] = Field(default_factory=list, description="自定义数据范围部门 ID 列表")
    dashboard_template: DashboardTemplate | None = Field(default=None, description="默认首页模板，空表示自动")
    sort: int = Field(default=0, ge=0)
    remark: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = None
    parent_id: int | None = None
    data_scope: int | None = Field(None, ge=1, le=5)
    data_scope_depts: list[int] | None = Field(None, description="自定义数据范围部门 ID 列表")
    dashboard_template: DashboardTemplate | None = Field(default=None, description="默认首页模板，空表示自动")
    sort: int | None = None
    status: int | None = Field(None, ge=0, le=1)
    remark: str | None = None


class RoleInfo(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    parent_id: int
    data_scope: int
    data_scope_depts: str | None  # JSON string
    dashboard_template: str | None
    sort: int
    status: int
    tenant_id: int | None
    is_system: bool

    class Config:
        from_attributes = True


class PermissionCreate(BaseModel):
    parent_id: int = Field(default=0)
    name: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=128)
    perm_type: str = Field(..., pattern="^(menu|button|column|api|data)$")
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    icon: str | None = None
    sort: int = Field(default=0, ge=0)
    is_visible: bool = True
    is_cache: bool = False
    is_external: bool = False
    resource: str | None = None
    method: str | None = None
    remark: str | None = None


class PermissionUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=64)
    code: str | None = Field(None, min_length=1, max_length=128)
    perm_type: str | None = Field(None, pattern="^(menu|button|column|api|data)$")
    path: str | None = None
    component: str | None = None
    redirect: str | None = None
    icon: str | None = None
    sort: int | None = Field(None, ge=0)
    is_visible: bool | None = None
    is_cache: bool | None = None
    is_external: bool | None = None
    resource: str | None = None
    method: str | None = None
    remark: str | None = None


class RolePermissionAssign(BaseModel):
    permission_ids: list[int]
