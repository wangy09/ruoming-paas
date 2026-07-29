"""
若茗 PaaS - 审计日志 Repository
提供审计日志、登录日志的数据访问方法
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import select, desc, func, delete

from app.core.base_repository import TenantAwareRepository
from app.modules.audit.models import SysAuditLog, SysLoginLog


class AuditRepository(TenantAwareRepository):
    """审计日志数据访问层"""

    def __init__(self, db, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_audit_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        username: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        status: int | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> tuple[list[SysAuditLog], int]:
        """查询审计日志列表"""
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        query = await self._base_query(SysAuditLog)
        query = query.order_by(desc(SysAuditLog.created_at))

        if username:
            query = query.where(SysAuditLog.username.ilike(f"%{username}%"))
        if action:
            query = query.where(SysAuditLog.action == action)
        if resource_type:
            query = query.where(SysAuditLog.resource_type == resource_type)
        if status is not None:
            query = query.where(SysAuditLog.status == status)
        if start_dt:
            query = query.where(SysAuditLog.created_at >= start_dt)
        if end_dt:
            query = query.where(SysAuditLog.created_at <= end_dt)

        return await self.paginate(query, page=page, page_size=page_size)

    async def delete_audit_logs(
        self,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        """删除审计日志，返回删除数量"""
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        # 先统计数量
        count_query = select(func.count(SysAuditLog.id)).where(SysAuditLog.is_deleted == False)
        if self.tenant_id is not None:
            count_query = count_query.where(SysAuditLog.tenant_id == self.tenant_id)
        if start_dt:
            count_query = count_query.where(SysAuditLog.created_at >= start_dt)
        if end_dt:
            count_query = count_query.where(SysAuditLog.created_at <= end_dt)
        total = await self.db.scalar(count_query) or 0

        # 执行软删除
        from sqlalchemy import update
        update_stmt = update(SysAuditLog).where(SysAuditLog.is_deleted == False)
        if self.tenant_id is not None:
            update_stmt = update_stmt.where(SysAuditLog.tenant_id == self.tenant_id)
        if start_dt:
            update_stmt = update_stmt.where(SysAuditLog.created_at >= start_dt)
        if end_dt:
            update_stmt = update_stmt.where(SysAuditLog.created_at <= end_dt)
        update_stmt = update_stmt.values(is_deleted=True)

        await self.db.execute(update_stmt)
        return total

    async def list_login_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        user_id: int | None = None,
    ) -> tuple[list[SysLoginLog], int]:
        """查询登录日志列表"""
        query = await self._base_query(SysLoginLog)
        query = query.order_by(desc(SysLoginLog.created_at))

        if user_id:
            query = query.where(SysLoginLog.user_id == user_id)

        return await self.paginate(query, page=page, page_size=page_size)
