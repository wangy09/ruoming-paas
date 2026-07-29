"""
若茗 PaaS - 用户路由
Author: ruoming
"""
from fastapi import APIRouter, Body, Depends, Query
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.redis import get_redis
from app.core.response import ApiResponse, ok, paged
from app.database import get_db, get_read_db
from app.modules.integration.contact_sync import ContactSyncService
from app.modules.integration.models import SysContactSyncLog
from app.modules.integration.schemas import (
    ContactSyncCheckResult,
    ContactSyncLogItem,
    ContactSyncPreviewResult,
    ContactSyncRequest,
    ContactSyncResult,
)
from app.modules.permission.service import PermissionService
from app.modules.user.schemas import (
    UserCreate,
    UserInfo,
    UserListItem,
    UserPasswordUpdate,
    UserRoleAssign,
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
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)

    # 获取当前用户的数据权限过滤
    perm_svc = PermissionService(db, redis)
    data_scope = await perm_svc.get_user_data_scope_filter(current_user.id, current_user.dept_id)

    items, total = await svc.get_list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        dept_id=dept_id,
        data_scope=data_scope,
    )
    return paged(
        items=[UserListItem.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/sync/preview",
    response_model=ApiResponse[ContactSyncPreviewResult],
    summary="预览第三方通讯录同步影响",
)
async def preview_sync_users_from_contacts(
    data: ContactSyncRequest,
    current_user=Depends(require_permissions("system:user:sync")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContactSyncPreviewResult]:
    svc = ContactSyncService(db, current_user)
    result = await svc.preview(data)
    await db.commit()
    return ok(result, message="预览完成")


@router.get(
    "/sync/logs",
    response_model=ApiResponse[list[ContactSyncLogItem]],
    summary="第三方通讯录同步日志",
)
async def list_contact_sync_logs(
    provider: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user=Depends(require_permissions("system:user:sync")),
    db: AsyncSession = Depends(get_read_db),
) -> ApiResponse[list[ContactSyncLogItem]]:
    conditions = [SysContactSyncLog.is_deleted == False]  # noqa: E712
    if not current_user.is_superplatform:
        conditions.append(SysContactSyncLog.tenant_id == current_user.tenant_id)
    if provider:
        conditions.append(SysContactSyncLog.provider == provider)
    result = await db.scalars(
        select(SysContactSyncLog)
        .where(*conditions)
        .order_by(SysContactSyncLog.created_at.desc())
        .limit(limit)
    )
    return ok([ContactSyncLogItem.model_validate(item) for item in result.all()])


@router.post(
    "/sync/check",
    response_model=ApiResponse[ContactSyncCheckResult],
    summary="第三方通讯录同步自检",
)
async def check_sync_users_from_contacts(
    data: ContactSyncRequest,
    current_user=Depends(require_permissions("system:user:sync")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContactSyncCheckResult]:
    svc = ContactSyncService(db, current_user)
    result = await svc.check(data)
    return ok(result, message="自检完成")


@router.post(
    "/sync",
    response_model=ApiResponse[ContactSyncResult],
    summary="从第三方通讯录同步用户",
)
async def sync_users_from_contacts(
    data: ContactSyncRequest,
    current_user=Depends(require_permissions("system:user:sync")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ContactSyncResult]:
    svc = ContactSyncService(db, current_user)
    result = await svc.sync(data)
    await db.commit()
    return ok(result, message="同步完成")


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
    db: AsyncSession = Depends(get_read_db),
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
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    await svc.delete_user(user_id)
    perm_svc = PermissionService(db, redis)
    await perm_svc.invalidate_user_permission_cache(user_id)
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
    data: UserRoleAssign,
    current_user=Depends(require_permissions("system:user:assign_role")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = UserService(db, tenant_id)
    await svc.assign_roles(user_id, data.role_ids)
    perm_svc = PermissionService(db, redis)
    await perm_svc.invalidate_user_permission_cache(user_id)
    return ok(message="角色分配成功")
