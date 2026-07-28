"""
若茗 PaaS - 审计日志 API
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
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
    username: str | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    status: int | None = Query(None, description="操作状态：1=成功 0=失败"),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    if start_time:
        start_dt = datetime.fromisoformat(start_time)
    if end_time:
        end_dt = datetime.fromisoformat(end_time)

    stmt = select(SysAuditLog).order_by(desc(SysAuditLog.created_at))
    if username:
        stmt = stmt.filter(SysAuditLog.username.ilike(f"%{username}%"))
    if action:
        stmt = stmt.filter(SysAuditLog.action == action)
    if resource_type:
        stmt = stmt.filter(SysAuditLog.resource_type == resource_type)
    if status is not None:
        stmt = stmt.filter(SysAuditLog.status == status)
    if start_dt:
        stmt = stmt.filter(SysAuditLog.created_at >= start_dt)
    if end_dt:
        stmt = stmt.filter(SysAuditLog.created_at <= end_dt)
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
            "status_code": item.status_code,
            "request_body": item.request_body,
            "response_body": item.response_body,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    return ok({"items": items, "total": total, "page": page_params.page, "page_size": page_params.page_size})


@router.delete("/logs")
async def delete_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:audit:clear"))],
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
):
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    if start_time:
        start_dt = datetime.fromisoformat(start_time)
    if end_time:
        end_dt = datetime.fromisoformat(end_time)

    stmt = select(func.count(SysAuditLog.id))
    if start_dt:
        stmt = stmt.filter(SysAuditLog.created_at >= start_dt)
    if end_dt:
        stmt = stmt.filter(SysAuditLog.created_at <= end_dt)
    if not current_user.is_superplatform:
        stmt = stmt.filter(SysAuditLog.tenant_id == current_user.tenant_id)
    count_before = await db.scalar(stmt)

    delete_stmt = delete(SysAuditLog)
    if start_dt:
        delete_stmt = delete_stmt.where(SysAuditLog.created_at >= start_dt)
    if end_dt:
        delete_stmt = delete_stmt.where(SysAuditLog.created_at <= end_dt)
    if not current_user.is_superplatform:
        delete_stmt = delete_stmt.where(SysAuditLog.tenant_id == current_user.tenant_id)

    result = await db.execute(delete_stmt)
    deleted_count = result.rowcount if result.rowcount is not None else 0

    await db.commit()

    return ok({"deleted_count": deleted_count})


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
