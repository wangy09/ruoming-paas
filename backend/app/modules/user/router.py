"""
若茗 PaaS - 用户路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.redis import get_redis
from app.core.response import ApiResponse, ok, paged
from app.database import get_db
from app.modules.user.schemas import (
    UserCreate,
    UserInfo,
    UserListParams,
    UserPasswordUpdate,
    UserUpdate,
)
from app.modules.user.service import UserService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse,
    summary="用户列表",
)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None, description="关键字搜索（用户名/昵称/邮箱）"),
    status: int | None = Query(default=None),
    dept_id: int | None = Query(default=None),
    current_user=Depends(require_permissions("system:user:view")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    items, total = await svc.get_list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        dept_id=dept_id,
    )
    return paged(
        items=[UserInfo.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[UserInfo],
    summary="创建用户",
    status_code=201,
)
async def create_user(
    data: UserCreate,
    current_user=Depends(require_permissions("system:user:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    user = await svc.create_user(data)
    return ApiResponse(code=201, message="创建成功", data=UserInfo.model_validate(user))


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserInfo],
    summary="用户详情",
)
async def get_user(
    user_id: int,
    current_user=Depends(require_permissions("system:user:view")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserInfo]:
    from app.core.exceptions import NotFoundException
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    user = await svc.get_by_id(user_id)
    if not user:
        raise NotFoundException("用户")
    return ok(UserInfo.model_validate(user))


@router.put(
    "/{user_id}",
    response_model=ApiResponse[UserInfo],
    summary="更新用户",
)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user=Depends(require_permissions("system:user:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    user = await svc.update_user(user_id, data)
    return ok(UserInfo.model_validate(user))


@router.delete(
    "/{user_id}",
    response_model=ApiResponse,
    summary="删除用户",
)
async def delete_user(
    user_id: int,
    current_user=Depends(require_permissions("system:user:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    await svc.delete_user(user_id)
    return ok(message="删除成功")


@router.put(
    "/{user_id}/password",
    response_model=ApiResponse,
    summary="修改密码",
)
async def change_password(
    user_id: int,
    data: UserPasswordUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    from app.core.exceptions import PermissionException

    # 只能修改自己的密码，或者有 reset_pwd 权限的管理员
    if current_user.id != user_id and not current_user.is_superplatform:
        raise PermissionException("只能修改自己的密码")

    svc = UserService(db)
    await svc.update_password(user_id, data.old_password, data.new_password)
    return ok(message="密码修改成功")


@router.post(
    "/{user_id}/roles",
    response_model=ApiResponse,
    summary="分配用户角色",
)
async def assign_user_roles(
    user_id: int,
    role_ids: list[int],
    current_user=Depends(require_permissions("system:user:assign_role")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    await svc.assign_roles(user_id, role_ids)
    return ok(message="角色分配成功")
