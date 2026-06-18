"""
若茗 PaaS - 请求日志中间件
记录每个请求的方法、路径、状态码、耗时，同时记录审计日志
Author: ruoming
"""
import asyncio
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token

logger = structlog.get_logger("access")

_SKIP_PATHS = frozenset([
    "/api/health",
    "/api/metrics",
    "/favicon.ico",
])

# 跳过审计日志的路径（如登录登出）
_SKIP_AUDIT_PATHS = frozenset([
    "/api/health",
    "/api/metrics",
    "/favicon.ico",
])

# 敏感资源列表 - 查询这些资源时强制记录审计日志
# （包括列表查询和单条详情，因为这些数据敏感度高）
_SENSITIVE_RESOURCES = frozenset([
    "users",  # 用户信息
    "api-keys",  # API密钥
    "permissions",  # 权限
    "roles",  # 角色
    "tenants",  # 租户
    "configs",  # 系统配置
])

# 导出/下载操作关键词
_EXPORT_KEYWORDS = frozenset([
    "export",
    "download",
])


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """结构化请求访问日志中间件，同时记录审计日志"""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        path = request.url.path
        method = request.method

        structlog.contextvars.bind_contextvars(
            request_ip=request_ip,
            user_agent=user_agent,
            path=path,
            method=method,
        )

        if path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response: Response | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            logger.exception("request_unhandled_error", exc_info=exc)
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            log_level = "warning" if status_code >= 400 else "info"
            getattr(logger, log_level)(
                "http_request",
                method=method,
                path=path,
                query=str(request.url.query) or None,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                client_ip=request_ip,
                user_agent=user_agent,
            )

            if path not in _SKIP_AUDIT_PATHS:
                await self._record_audit_log(request, path, method, status_code, request_ip, user_agent)

    async def _record_audit_log(self, request: Request, path: str, method: str, status_code: int, request_ip: str | None = None, user_agent: str | None = None) -> None:
        """记录审计日志"""
        status = 1 if 200 <= status_code < 400 else 0
        error_msg = f"HTTP {status_code}" if status_code >= 400 else None

        ctx = structlog.contextvars.get_contextvars()

        user_id = ctx.get("user_id")
        username = ctx.get("username")
        tenant_id = ctx.get("tenant_id")

        if user_id is None:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = decode_access_token(token)
                    user_id = int(payload.get("sub", 0)) if payload.get("sub") else None
                    username = payload.get("username")
                    tenant_id = payload.get("tid")
                except Exception:
                    pass

        event_type = f"{method.lower()}.{path.replace('/', '.').strip('.')}"
        parts = path.strip("/").split("/")
        module = parts[1] if len(parts) >= 2 and parts[0] == "api" else None
        resource_type = parts[2] if len(parts) >= 3 and parts[0] == "api" else None

        # 根据策略判断是否需要记录审计日志
        if not self._should_record_audit_log(method, path, resource_type):
            return

        resource_id = None
        if len(parts) >= 4 and parts[0] == "api":
            try:
                int(parts[3])
                resource_id = parts[3]
            except ValueError:
                pass
        elif len(parts) >= 3 and parts[0] == "api":
            try:
                int(parts[2])
                resource_id = parts[2]
            except ValueError:
                pass

        trace_id = getattr(request.state, "trace_id", None) or ctx.get("trace_id")

        browser, os_name, device = self._parse_user_agent(user_agent)

        await self._write_audit_log(
            event_type=event_type,
            module=module,
            action=method.lower(),
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_msg=error_msg,
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            request_ip=request_ip,
            user_agent=user_agent,
            browser=browser,
            os=os_name,
            device=device,
            trace_id=trace_id,
            path=path,
            method=method,
        )

    async def _write_audit_log(
        self,
        event_type: str,
        module: str | None,
        action: str | None,
        resource_type: str | None,
        resource_id: str | None,
        status: int,
        error_msg: str | None,
        user_id: int | None = None,
        username: str | None = None,
        tenant_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        browser: str | None = None,
        os: str | None = None,
        device: str | None = None,
        trace_id: str | None = None,
        path: str | None = None,
        method: str | None = None,
    ) -> None:
        """异步写审计日志"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.audit.service import AuditService

            async with AsyncSessionFactory() as db:
                svc = AuditService(db)
                await svc.record(
                    event_type=event_type,
                    module=module,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status=status,
                    error_msg=error_msg,
                    user_id=user_id,
                    username=username,
                    tenant_id=tenant_id,
                    request_ip=request_ip,
                    user_agent=user_agent,
                    browser=browser,
                    os=os,
                    device=device,
                    trace_id=trace_id,
                    path=path,
                    method=method,
                )
                await db.commit()
        except Exception as e:
            logger.error("audit_log_write_failed", event_type=event_type, error=str(e))

    def _parse_user_agent(self, user_agent: str | None) -> tuple[str | None, str | None, str | None]:
        """解析 User-Agent，提取浏览器、操作系统、设备类型"""
        if not user_agent:
            return None, None, None

        browser = None
        os_name = None
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
            os_name = 'Windows'
            device = 'Desktop'
        elif 'mac os' in ua or 'macos' in ua:
            os_name = 'MacOS'
            device = 'Desktop'
        elif 'linux' in ua and 'android' not in ua:
            os_name = 'Linux'
            device = 'Desktop'
        elif 'android' in ua:
            os_name = 'Android'
            if 'mobile' in ua or 'phone' in ua:
                device = 'Mobile'
            else:
                device = 'Tablet'
        elif 'iphone' in ua or 'ipad' in ua:
            os_name = 'iOS'
            device = 'Mobile' if 'iphone' in ua else 'Tablet'

        return browser, os_name, device

    def _should_record_audit_log(self, method: str, path: str, resource_type: str | None) -> bool:
        """
        判断是否需要记录审计日志

        记录策略：
        - 写操作（POST/PUT/DELETE/PATCH）：必须记录
        - 导出/下载操作：必须记录
        - 单条详情查询（带数字ID）：必须记录
        - 敏感资源查询（包括列表）：必须记录
        - 普通列表查询：不记录

        区分标准：数据敏感度 + 操作类型 + 查询数据范围
        避免日志爆炸：只记录高敏感度操作，普通查询不记录
        """
        # 写操作必须记录（创建、更新、删除）
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            return True

        # GET请求进一步判断
        if method == "GET":
            # 检查是否包含导出/下载关键词
            path_lower = path.lower()
            for keyword in _EXPORT_KEYWORDS:
                if keyword in path_lower:
                    return True

            # 单条详情查询（路径包含数字ID）必须记录
            # 例如：/api/v1/users/123, /api/v1/users/123/profile
            parts = path.strip("/").split("/")
            has_numeric_id = any(part.isdigit() for part in parts)

            if has_numeric_id:
                return True

            # 敏感资源列表查询也必须记录（用户、权限、角色等敏感数据）
            if resource_type and resource_type in _SENSITIVE_RESOURCES:
                return True

        # 其他情况不记录（普通列表查询如 /api/v1/knowledge-bases）
        return False
