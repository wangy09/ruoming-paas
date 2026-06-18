"""
若茗 PaaS - 权限模块 Pydantic 模型
Author: ruoming
"""
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_:]+$")
    description: str | None = None
    parent_id: int = Field(default=0, description="父角色 ID（0=无父角色）")
    data_scope: int = Field(default=1, ge=1, le=5)
    sort: int = Field(default=0, ge=0)
    remark: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = None
    parent_id: int | None = None
    data_scope: int | None = Field(None, ge=1, le=5)
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
    sort: int
    status: int
    tenant_id: int | None

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


class RolePermissionAssign(BaseModel):
    permission_ids: list[int]
