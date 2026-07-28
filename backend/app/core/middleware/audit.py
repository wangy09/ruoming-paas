"""
若茗 PaaS - 审计日志中间件
自动记录所有 API 请求的操作日志
Author: ruoming
"""
import json

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.utils import fire_and_forget


class AuditMiddleware(BaseHTTPMiddleware):
    """
    审计日志中间件：
    - 在请求开始时绑定请求信息到 structlog 上下文
    - 在请求结束后自动记录操作审计日志
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        path = request.url.path
        method = request.method

        structlog.contextvars.bind_contextvars(
            request_ip=request_ip,
            user_agent=user_agent,
            path=path,
            method=method,
        )

        status_code = 200
        request_body = None
        response_body = None
        error_msg = None

        try:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                try:
                    body = await request.json()
                    request_body = self._sanitize_body(body)
                except Exception:
                    pass

            response = await call_next(request)
            status_code = response.status_code

            if status_code >= 400:
                response_body, response = await self._get_response_body(response)

            return response

        except Exception as e:
            status_code = 500
            error_msg = str(e)
            raise

        finally:
            await self._record_audit_log(
                request=request,
                path=path,
                method=method,
                status_code=status_code,
                request_body=request_body,
                response_body=response_body,
                error_msg=error_msg,
                request_ip=request_ip,
                user_agent=user_agent,
            )

    def _get_client_ip(self, request: Request) -> str | None:
        """获取客户端真实 IP"""
        headers = request.headers
        for header in ("X-Forwarded-For", "X-Real-IP", "Proxy-Client-IP", "WL-Proxy-Client-IP"):
            ip = headers.get(header)
            if ip:
                return ip.split(",")[0].strip()
        return request.client.host if request.client else None

    def _sanitize_body(self, body: dict) -> dict:
        """
        清理请求体，移除敏感信息。
        """
        sensitive_fields = {"password", "old_password", "new_password", "secret", "token", "access_token", "refresh_token"}
        result: dict = {}
        for key, value in body.items():
            if key.lower() in sensitive_fields:
                result[key] = "******"
            elif isinstance(value, dict):
                result[key] = self._sanitize_body(value)
            else:
                result[key] = value
        return result

    async def _get_response_body(self, response: Response) -> tuple[str | None, Response]:
        """获取响应体内容并重新构造响应"""
        try:
            body = b""
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body += chunk
                response_headers = dict(response.headers)
                response_headers.pop("Content-Length", None)
                response = Response(
                    content=body,
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.media_type,
                )
            elif hasattr(response, "body"):
                body_bytes = response.body
                if isinstance(body_bytes, memoryview):
                    body = bytes(body_bytes)
                elif isinstance(body_bytes, bytes):
                    body = body_bytes
                else:
                    return None, response
            else:
                return None, response
            return body.decode("utf-8", errors="ignore")[:2000], response
        except Exception:
            return None, response

    async def _record_audit_log(
        self,
        request: Request,
        path: str,
        method: str,
        status_code: int,
        request_body: dict | None,
        response_body: str | None,
        error_msg: str | None,
        request_ip: str | None,
        user_agent: str | None,
    ) -> None:
        """异步记录审计日志"""
        ctx = structlog.contextvars.get_contextvars()
        user_id = ctx.get("user_id")
        username = ctx.get("username")
        tenant_id = ctx.get("tenant_id")
        trace_id = ctx.get("trace_id")

        if not user_id and hasattr(request.state, "user"):
            user = request.state.user
            user_id = getattr(user, "id", None)
            username = getattr(user, "username", None)

        if path.startswith("/api/v1/auth/login"):
            return

        if path.startswith("/api/v1/audit/"):
            return

        fire_and_forget(
            self._write_log_async(
                event_type=f"{method.lower()}.{path.replace('/', '.').strip('.')}",
                path=path,
                method=method,
                status_code=status_code,
                request_body=request_body,
                response_body=response_body if status_code < 500 else None,
                error_msg=error_msg,
                user_id=user_id,
                username=username,
                tenant_id=tenant_id,
                request_ip=request_ip,
                user_agent=user_agent,
                trace_id=trace_id,
            ),
            name=f"audit_log_{method}_{path[:50]}",
            timeout=30.0,
        )

    async def _write_log_async(
        self,
        event_type: str,
        path: str,
        method: str,
        status_code: int,
        request_body: dict | None,
        response_body: str | None,
        error_msg: str | None,
        user_id: int | None,
        username: str | None,
        tenant_id: int | None,
        request_ip: str | None,
        user_agent: str | None,
        trace_id: str | None,
    ) -> None:
        """异步写入审计日志"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.audit.service import AuditService

            async with AsyncSessionFactory() as db:
                svc = AuditService(db)
                await svc.record(
                    event_type=event_type,
                    module=path.split("/")[3] if len(path.split("/")) > 3 else None,
                    action=method.lower(),
                    resource_type=path.split("/")[4] if len(path.split("/")) > 4 else None,
                    user_id=user_id,
                    username=username,
                    tenant_id=tenant_id,
                    request_body=request_body,
                    response_body=self._parse_json(response_body),
                    status_code=status_code,
                    request_ip=request_ip,
                    user_agent=user_agent,
                    trace_id=trace_id,
                    path=path,
                    method=method,
                    status=1 if status_code < 400 else 0,
                    error_msg=error_msg,
                )
                await db.commit()
        except Exception as e:
            structlog.get_logger(__name__).error("audit_log_write_failed", error=str(e))

    @staticmethod
    def _parse_json(text: str | None) -> dict | None:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None