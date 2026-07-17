"""
若茗 PaaS - 租户管理路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_superplatform
from app.core.response import ApiResponse, ok, paged
from app.database import get_db
from app.modules.tenant.schemas import (
    TenantCreate,
    TenantInfo,
    TenantListItem,
    TenantUpdate,
    TenantQuotaUpdate,
    TenantApprove,
)
from app.modules.tenant.service import TenantService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse,
    summary="租户列表",
)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = Query(default=None, description="关键字搜索（名称/标识）"),
    status: str | None = Query(default=None, description="状态"),
    plan: str | None = Query(default=None, description="套餐"),
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    status_int = int(status) if status and status.strip() else None
    plan_clean = plan if plan and plan.strip() else None

    svc = TenantService(db)
    items, total = await svc.get_list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status_int,
        plan=plan_clean,
    )
    return paged(
        items=[TenantListItem.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[TenantInfo],
    summary="创建租户",
    status_code=201,
)
async def create_tenant(
    data: TenantCreate,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    tenant = await svc.create(data, registered_by=current_user.id)
    return ApiResponse(code=201, message="创建成功", data=TenantInfo.model_validate(tenant))


@router.get(
    "/{tenant_id}",
    response_model=ApiResponse[TenantInfo],
    summary="租户详情",
)
async def get_tenant(
    tenant_id: int,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    tenant = await svc.get_by_id(tenant_id)
    if not tenant:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("租户")
    return ok(TenantInfo.model_validate(tenant))


@router.put(
    "/{tenant_id}",
    response_model=ApiResponse[TenantInfo],
    summary="更新租户",
)
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    tenant = await svc.update(tenant_id, data)
    return ok(TenantInfo.model_validate(tenant))


@router.put(
    "/{tenant_id}/quota",
    response_model=ApiResponse[TenantInfo],
    summary="更新租户配额",
)
async def update_tenant_quota(
    tenant_id: int,
    data: TenantQuotaUpdate,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    tenant = await svc.update_quota(tenant_id, data)
    return ok(TenantInfo.model_validate(tenant))


@router.post(
    "/{tenant_id}/approve",
    response_model=ApiResponse[TenantInfo],
    summary="审核租户",
)
async def approve_tenant(
    tenant_id: int,
    data: TenantApprove,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    tenant = await svc.approve(tenant_id, data, approved_by=current_user.id)
    return ok(TenantInfo.model_validate(tenant))


@router.delete(
    "/{tenant_id}",
    response_model=ApiResponse,
    summary="删除租户",
)
async def delete_tenant(
    tenant_id: int,
    current_user=Depends(require_superplatform()),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    svc = TenantService(db)
    await svc.delete(tenant_id)
    return ok(message="删除成功")