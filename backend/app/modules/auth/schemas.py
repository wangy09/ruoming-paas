"""
若茗 PaaS - 认证模块 Pydantic 模型
Author: ruoming
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    tenant_code: str | None = Field(None, description="租户标识（多租户场景）")


class LoginResponse(BaseModel):
    """登录成功响应"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int           # access_token 有效期（秒）
    user_id: int
    username: str
    nickname: str | None
    is_superplatform: bool
    tenant_id: int | None


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Token 刷新成功响应"""

    access_token: str
    refresh_token: str          # Rotation 轮换后的新 Refresh Token
    token_type: str = "Bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    """登出请求"""

    refresh_token: str | None = None
