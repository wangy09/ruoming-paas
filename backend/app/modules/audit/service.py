"""
若茗 PaaS - 审计服务
提供操作审计日志、登录日志、安全事件记录
Author: ruoming
"""
import asyncio
import functools
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import SysAuditLog, SysLoginLog, SysSecurityEvent

logger = structlog.get_logger(__name__)


class AuditService:
    """审计日志服务（非阻塞写入）"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        *,
        event_type: str,
        module: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
        tenant_id: int | None = None,
        before_data: dict | None = None,
        after_data: dict | None = None,
        detail: dict | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        browser: str | None = None,
        os: str | None = None,
        device: str | None = None,
        trace_id: str | None = None,
        path: str | None = None,
        method: str | None = None,
        status: int = 1,
        error_msg: str | None = None,
    ) -> None:
        """
        记录操作审计日志。
        通常在 Service 层写操作完成后调用，传入 before/after 数据快照。
        """
        ctx = structlog.contextvars.get_contextvars()

        log = SysAuditLog(
            tenant_id=tenant_id or ctx.get("tenant_id"),
            user_id=user_id or ctx.get("user_id"),
            username=username or ctx.get("username"),
            module=module,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            event_type=event_type,
            before_data=before_data,
            after_data=after_data,
            detail=detail,
            request_ip=request_ip,
            user_agent=user_agent,
            browser=browser,
            os=os,
            device=device,
            trace_id=trace_id or ctx.get("trace_id"),
            path=path,
            method=method,
            status=status,
            error_msg=error_msg,
        )
        self.db.add(log)
        # 调用方负责 commit

    async def record_login(
        self,
        *,
        username: str,
        status: int,
        user_id: int | None = None,
        tenant_id: int | None = None,
        login_type: str = "password",
        fail_reason: str | None = None,
        login_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录登录日志"""
        ctx = structlog.contextvars.get_contextvars()
        browser, os, device = self._parse_user_agent(user_agent)
        log = SysLoginLog(
            tenant_id=tenant_id or ctx.get("tenant_id"),
            user_id=user_id,
            username=username,
            login_type=login_type,
            status=status,
            fail_reason=fail_reason,
            login_ip=login_ip,
            user_agent=user_agent,
            browser=browser,
            os=os,
            device=device,
        )
        self.db.add(log)

    def _parse_user_agent(self, user_agent: str | None) -> tuple[str | None, str | None, str | None]:
        """解析 User-Agent，提取浏览器、操作系统、设备类型"""
        if not user_agent:
            return None, None, None

        browser = None
        os = None
        device = None

        ua = user_agent.lower()

        if 'edg' in ua:
            browser = 'Edge'
        elif 'chrome' in ua and 'edg' not in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua and 'chrome' not in ua:
            browser = 'Safari'
        elif 'opera' in ua or 'opr' in ua:
            browser = 'Opera'

        if 'windows' in ua:
            os = 'Windows'
            device = 'Desktop'
        elif 'mac os' in ua or 'macos' in ua:
            os = 'MacOS'
            device = 'Desktop'
        elif 'linux' in ua and 'android' not in ua:
            os = 'Linux'
            device = 'Desktop'
        elif 'android' in ua:
            os = 'Android'
            if 'mobile' in ua or 'phone' in ua:
                device = 'Mobile'
            else:
                device = 'Tablet'
        elif 'iphone' in ua or 'ipad' in ua:
            os = 'iOS'
            device = 'Mobile' if 'iphone' in ua else 'Tablet'

        return browser, os, device

    async def record_security_event(
        self,
        *,
        event_type: str,
        severity: str = "warning",
        user_id: int | None = None,
        tenant_id: int | None = None,
        detail: dict | None = None,
        source_ip: str | None = None,
    ) -> None:
        """记录安全事件（暴力破解、Token 重放、跨租户访问等）"""
        ctx = structlog.contextvars.get_contextvars()
        event = SysSecurityEvent(
            tenant_id=tenant_id or ctx.get("tenant_id"),
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            detail=detail,
            source_ip=source_ip,
            trace_id=ctx.get("trace_id"),
        )
        self.db.add(event)
        logger.warning(
            "security_event",
            event_type=event_type,
            severity=severity,
            user_id=user_id,
        )


def audit_log(
    event_type: str,
    module: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
):
    """
    操作审计装饰器。
    自动记录函数调用前后的状态（需要 Service 函数返回操作结果）。

    用法::

        @audit_log("user.update", module="user", action="update", resource_type="sys_user")
        async def update_user(self, user_id: int, data: dict) -> SysUser:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            result = None
            error_msg = None
            status = 1
            try:
                result = await func(self, *args, **kwargs)
                return result
            except Exception as e:
                status = 0
                error_msg = str(e)
                raise
            finally:
                ctx = structlog.contextvars.get_contextvars()
                asyncio.create_task(
                    _write_audit_log_async(
                        event_type=event_type,
                        module=module,
                        action=action,
                        resource_type=resource_type,
                        status=status,
                        error_msg=error_msg,
                        user_id=ctx.get("user_id"),
                        username=ctx.get("username"),
                        tenant_id=ctx.get("tenant_id"),
                        request_ip=ctx.get("request_ip"),
                        user_agent=ctx.get("user_agent"),
                        trace_id=ctx.get("trace_id"),
                        path=ctx.get("path"),
                        method=ctx.get("method"),
                    )
                )
        return wrapper
    return decorator


async def _write_audit_log_async(
    event_type: str,
    module: str | None,
    action: str | None,
    resource_type: str | None,
    status: int,
    error_msg: str | None,
    user_id: int | None = None,
    username: str | None = None,
    tenant_id: int | None = None,
    request_ip: str | None = None,
    user_agent: str | None = None,
    trace_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
) -> None:
    """异步写审计日志（独立 Session，不依赖外部事务）"""
    try:
        from app.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            svc = AuditService(db)
            await svc.record(
                event_type=event_type,
                module=module,
                action=action,
                resource_type=resource_type,
                status=status,
                error_msg=error_msg,
                user_id=user_id,
                username=username,
                tenant_id=tenant_id,
                request_ip=request_ip,
                user_agent=user_agent,
                trace_id=trace_id,
                path=path,
                method=method,
            )
            await db.commit()
    except Exception as e:
        logger.error("audit_log_write_failed", event_type=event_type, error=str(e))
