"""
若茗 PaaS - 认证路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.core.response import ApiResponse, ok
from app.database import get_db
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="用户登录",
    description="用户名/密码登录，返回 Access Token 和 Refresh Token",
)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse[LoginResponse]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    svc = AuthService(db, redis)
    result = await svc.login(req, client_ip=client_ip, user_agent=user_agent)
    return ok(result, message="登录成功")


@router.post(
    "/refresh",
    response_model=ApiResponse[RefreshTokenResponse],
    summary="刷新 Token",
    description="使用 Refresh Token 获取新的 Access Token（Rotation 轮换，每个 Token 只能使用一次）",
)
async def refresh_token(
    req: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse[RefreshTokenResponse]:
    svc = AuthService(db, redis)
    result = await svc.refresh_token(req.refresh_token)
    return ok(result)


@router.post(
    "/logout",
    response_model=ApiResponse,
    summary="登出",
    description="撤销 Refresh Token，使当前会话失效",
)
async def logout(
    req: LogoutRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    svc = AuthService(db, redis)
    await svc.logout(current_user.id, req.refresh_token)
    return ok(message="已登出")


@router.get(
    "/me",
    response_model=ApiResponse,
    summary="获取当前用户信息",
)
async def get_me(current_user=Depends(get_current_user)) -> ApiResponse:
    return ok({
        "id": current_user.id,
        "username": current_user.username,
        "nickname": current_user.nickname,
        "email": current_user.email,
        "avatar": current_user.avatar,
        "is_superplatform": current_user.is_superplatform,
        "tenant_id": current_user.tenant_id,
        "dept_id": current_user.dept_id,
        "status": current_user.status,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    })
