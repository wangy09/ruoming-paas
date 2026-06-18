content = '''from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.modules.audit.models import SysAuditLog, SysLoginLog
from app.core.deps import get_current_user
from app.modules.user.models import SysUser
from app.core.response import ok
from app.schemas import PageParams
router = APIRouter()

@router.get("/logs")
async def list_audit_logs(db: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[SysUser, Depends(get_current_user)], page_params: Annotated[PageParams, Depends()], action: str | None = Query(None), resource_type: str | None = Query(None), start_time: str | None = Query(None), end_time: str | None = Query(None)):
    stmt = select(SysAuditLog).order_by(desc(SysAuditLog.created_at))
    if action: stmt = stmt.filter(SysAuditLog.action == action)
    if resource_type: stmt = stmt.filter(SysAuditLog.resource_type == resource_type)
    if start_time: stmt = stmt.filter(SysAuditLog.created_at >= start_time)
    if end_time: stmt = stmt.filter(SysAuditLog.created_at <= end_time)
    if not current_user.is_superplatform: stmt = stmt.filter(SysAuditLog.tenant_id == current_user.tenant_id)
    total = await db.scalar(select(SysAuditLog.id).filter(*stmt.whereclause).count())
    rows = await db.execute(stmt.offset((page_params.page - 1) * page_params.page_size).limit(page_params.page_size))
    return ok({"items": rows.scalars().all(), "total": total, "page": page_params.page, "page_size": page_params.page_size})

@router.get("/login-logs")
async def list_login_logs(db: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[SysUser, Depends(get_current_user)], page_params: Annotated[PageParams, Depends()], user_id: int | None = Query(None)):
    stmt = select(SysLoginLog).order_by(desc(SysLoginLog.created_at))
    if user_id: stmt = stmt.filter(SysLoginLog.user_id == user_id)
    if not current_user.is_superplatform: stmt = stmt.filter(SysLoginLog.tenant_id == current_user.tenant_id)
    total = await db.scalar(select(SysLoginLog.id).filter(*stmt.whereclause).count())
    rows = await db.execute(stmt.offset((page_params.page - 1) * page_params.page_size).limit(page_params.page_size))
    return ok({"items": rows.scalars().all(), "total": total, "page": page_params.page, "page_size": page_params.page_size})
'''
with open("/Users/wangyan/Documents/Projects/01_Working/RuoMingPaas/backend/app/modules/audit/router.py", "w") as f:
    f.write(content)
print("router.py