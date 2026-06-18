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
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    dept_id: int | None = None
    role_ids: list[int] = Field(default_factory=list)
    tenant_id: int | None = None


class UserUpdate(BaseModel):
    """更新用户"""

    nickname: str | None = Field(None, max_length=64)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    dept_id: int | None = None
    status: int | None = Field(None, ge=0, le=1)
    remark: str | None = None


class UserPasswordUpdate(BaseModel):
    """修改密码"""

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


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
    tenant_id: int | None
    last_login: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class UserListParams(BaseModel):
    """用户列表查询参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    keyword: str | None = None
    status: int | None = None
    dept_id: int | None = None
