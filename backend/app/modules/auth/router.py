"""
若茗 PaaS - 认证路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import limiter, get_ip_key, get_user_key
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
from app.modules.auth.captcha import CaptchaService

router = APIRouter()


@router.get(
    "/captcha",
    response_model=ApiResponse,
    summary="获取验证码",
)
@limiter.limit("3/minute", key_func=get_ip_key)
async def get_captcha(request: Request, redis: Redis = Depends(get_redis)) -> ApiResponse:
    """获取图形验证码"""
    svc = CaptchaService(redis)
    result = await svc.generate_captcha()
    return ok({
        "key": result["key"],
        "image": result["image"],
    })


@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="用户登录",
    description="用户名/密码登录，返回 Access Token 和 Refresh Token",
)
@limiter.limit("10/minute", key_func=get_ip_key)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse[LoginResponse]:
    from app.core.exceptions import BusinessException

    # 校验验证码
    captcha_svc = CaptchaService(redis)
    if not await captcha_svc.verify_captcha(req.captcha_key, req.captcha_code):
        raise BusinessException(code=40002, message="验证码错误", http_status=400)

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
@limiter.limit("20/minute", key_func=get_ip_key)
async def refresh_token(
    req: RefreshTokenRequest,
    request: Request,
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
async def get_me(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    from app.modules.permission.models import SysRole, SysUserRole
    from sqlalchemy import select

    # 获取用户角色
    result = await db.execute(
        select(SysRole)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .where(SysUserRole.user_id == current_user.id, SysRole.is_deleted == False)
        .order_by(SysRole.sort, SysRole.id)
    )
    roles = list(result.scalars().all())

    return ok({
        "id": current_user.id,
        "username": current_user.username,
        "nickname": current_user.nickname,
        "email": current_user.email,
        "phone": current_user.phone,
        "avatar": current_user.avatar,
        "is_superplatform": current_user.is_superplatform,
        "tenant_id": current_user.tenant_id,
        "dept_id": current_user.dept_id,
        "status": current_user.status,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "code": r.code,
                "dashboard_template": r.dashboard_template,
            }
            for r in roles
        ],
    })


from app.modules.user.schemas import UserPasswordUpdate


@router.put(
    "/me/password",
    response_model=ApiResponse,
    summary="修改当前用户密码",
)
async def change_my_password(
    data: UserPasswordUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    from app.modules.user.service import UserService

    svc = UserService(db)
    await svc.update_password(current_user.id, data.old_password, data.new_password)
    return ok(message="密码修改成功")
