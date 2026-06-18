"""
若茗 PaaS - 审计日志 API
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ok
from app.database import get_db
from app.modules.audit.models import SysAuditLog, SysLoginLog
from app.modules.user.models import SysUser
from app.core.utils.pagination import PageParams

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    stmt = select(SysAuditLog).order_by(desc(SysAuditLog.created_at))
    if action:
        stmt = stmt.filter(SysAuditLog.action == action)
    if resource_type:
        stmt = stmt.filter(SysAuditLog.resource_type == resource_type)
    if start_time:
        stmt = stmt.filter(SysAuditLog.created_at >= start_time)
    if end_time:
        stmt = stmt.filter(SysAuditLog.created_at <= end_time)
    if not current_user.is_superplatform:
        stmt = stmt.filter(SysAuditLog.tenant_id == current_user.tenant_id)
    count_stmt = select(func.count(SysAuditLog.id))
    if stmt.whereclause is not None:
        count_stmt = count_stmt.filter(stmt.whereclause)
    total = await db.scalar(count_stmt)
    rows = await db.execute(stmt.offset((page_params.page - 1) * page_params.page_size).limit(page_params.page_size))
    items = []
    for item in rows.scalars().all():
        items.append({
            "id": item.id,
            "tenant_id": item.tenant_id,
            "user_id": item.user_id,
            "username": item.username,
            "module": item.module,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "event_type": item.event_type,
            "status": item.status,
            "error_msg": item.error_msg,
            "request_ip": item.request_ip,
            "user_agent": item.user_agent,
            "browser": item.browser,
            "os": item.os,
            "device": item.device,
            "trace_id": item.trace_id,
            "path": item.path,
            "method": item.method,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    return ok({"items": items, "total": total, "page": page_params.page, "page_size": page_params.page_size})


@router.get("/login-logs")
async def list_login_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    user_id: int | None = Query(None),
):
    stmt = select(SysLoginLog).order_by(desc(SysLoginLog.created_at))
    if user_id:
        stmt = stmt.filter(SysLoginLog.user_id == user_id)
    if not current_user.is_superplatform:
        stmt = stmt.filter(SysLoginLog.tenant_id == current_user.tenant_id)
    count_stmt = select(func.count(SysLoginLog.id))
    if stmt.whereclause is not None:
        count_stmt = count_stmt.filter(stmt.whereclause)
    total = await db.scalar(count_stmt)
    rows = await db.execute(stmt.offset((page_params.page - 1) * page_params.page_size).limit(page_params.page_size))
    items = []
    for item in rows.scalars().all():
        items.append({
            "id": item.id,
            "tenant_id": item.tenant_id,
            "user_id": item.user_id,
            "username": item.username,
            "login_type": item.login_type,
            "status": item.status,
            "fail_reason": item.fail_reason,
            "login_ip": item.login_ip,
            "user_agent": item.user_agent,
            "device": item.device,
            "browser": item.browser,
            "os": item.os,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    return ok({"items": items, "total": total, "page": page_params.page, "page_size": page_params.page_size})
