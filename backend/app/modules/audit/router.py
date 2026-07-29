"""
若茗 PaaS - 审计日志 API
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.response import ok
from app.database import get_db, get_read_db
from app.modules.audit.service import AuditService
from app.modules.user.models import SysUser
from app.core.utils.pagination import PageParams

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_read_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    username: str | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    status: int | None = Query(None, description="操作状态：1=成功 0=失败"),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    svc = AuditService(db, None if current_user.is_superplatform else current_user.tenant_id)
    items, total = await svc.list_audit_logs(
        page=page_params.page,
        page_size=page_params.page_size,
        username=username,
        action=action,
        resource_type=resource_type,
        status=status,
        start_time=start_time,
        end_time=end_time,
        tenant_id=current_user.tenant_id,
        is_superplatform=current_user.is_superplatform,
    )
    return ok({"items": items, "total": total, "page": page_params.page, "page_size": page_params.page_size})


@router.delete("/logs")
async def delete_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:audit:clear"))],
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    svc = AuditService(db, None if current_user.is_superplatform else current_user.tenant_id)
    deleted_count = await svc.delete_audit_logs(
        start_time=start_time,
        end_time=end_time,
        tenant_id=current_user.tenant_id,
        is_superplatform=current_user.is_superplatform,
    )
    await db.commit()
    return ok({"deleted_count": deleted_count})


@router.get("/login-logs")
async def list_login_logs(
    db: Annotated[AsyncSession, Depends(get_read_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    user_id: int | None = Query(None),
):
    svc = AuditService(db, None if current_user.is_superplatform else current_user.tenant_id)
    items, total = await svc.list_login_logs(
        page=page_params.page,
        page_size=page_params.page_size,
        user_id=user_id,
        tenant_id=current_user.tenant_id,
        is_superplatform=current_user.is_superplatform,
    )
    return ok({"items": items, "total": total, "page": page_params.page, "page_size": page_params.page_size})
