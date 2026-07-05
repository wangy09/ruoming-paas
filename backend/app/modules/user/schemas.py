"""
若茗 PaaS - 用户模块 Pydantic 模型
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """创建用户"""

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    nickname: str | None = Field(None, max_length=64)
    email: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=20)
    dept_id: int | None = None
    role_ids: list[int] = Field(default_factory=list)
    tenant_id: int | None = None


class UserUpdate(BaseModel):
    """更新用户"""

    nickname: str | None = Field(None, max_length=64)
    email: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=20)
    dept_id: int | None = None
    status: int | None = Field(None, ge=0, le=1)
    remark: str | None = None


class UserPasswordUpdate(BaseModel):
    """修改密码"""

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserRoleAssign(BaseModel):
    """分配角色请求"""
    role_ids: list[int] = Field(..., description="角色 ID 列表")


class UserInfo(BaseModel):
    """用户信息响应"""

    id: int
    username: str
    nickname: str | None
    email: str | None
    phone: str | None
    avatar: str | None
    status: int
    is_superplatform: bool
    dept_id: int | None
    dept_name: str | None = None
    tenant_id: int | None
    last_login: datetime | None
    created_at: datetime
    roles: list[dict] = Field(default_factory=list, description="用户角色列表")

    class Config:
        from_attributes = True


class UserListItem(UserInfo):
    """用户列表项响应，包含账号来源标识。"""

    source_type: str = Field(default="local", description="来源类型：local/external")
    source_provider: str | None = Field(None, description="外部通讯录平台")
    source_connection_id: int | None = Field(None, description="外部集成连接 ID")
    source_connection_name: str | None = Field(None, description="外部集成连接名称")
    source_external_id: str | None = Field(None, description="外部通讯录用户 ID")


class UserListParams(BaseModel):
    """用户列表查询参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    keyword: str | None = None
    status: int | None = None
    dept_id: int | None = None
