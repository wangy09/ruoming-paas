"""
若茗 PaaS - 请求日志中间件
记录每个请求的方法、路径、请求体、状态码、响应体、耗时，同时记录审计日志
Author: ruoming
"""
import asyncio
import json
import time
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message

from app.core.security import decode_access_token

logger = structlog.get_logger("access")

_SKIP_PATHS = frozenset([
    "/api/health",
    "/api/metrics",
    "/favicon.ico",
])

# 跳过审计日志的路径
_SKIP_AUDIT_PATHS = frozenset([
    "/api/health",
    "/api/metrics",
    "/favicon.ico",
])

# 敏感资源列表 - 查询这些资源时强制记录审计日志
_SENSITIVE_RESOURCES = frozenset([
    "users",
    "api-keys",
    "permissions",
    "roles",
    "tenants",
    "configs",
])

# 导出/下载操作关键词
_EXPORT_KEYWORDS = frozenset([
    "export",
    "download",
])

# 请求体/响应体中需要脱敏的字段（置为 "***"）
_SENSITIVE_FIELDS = frozenset([
    "password", "passwd", "secret", "token", "access_token",
    "refresh_token", "api_key", "private_key", "card_no",
])

# 响应体大小上限（字节），超过此值截断，避免存储爆炸
_RESPONSE_BODY_MAX_BYTES = 8 * 1024  # 8 KB


def _desensitize(data: Any, depth: int = 0) -> Any:
    """递归脱敏字典/列表中的敏感字段，最多递归 5 层"""
    if depth > 5:
        return data
    if isinstance(data, dict):
        return {
            k: "***" if k.lower() in _SENSITIVE_FIELDS else _desensitize(v, depth + 1)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_desensitize(item, depth + 1) for item in data]
    return data


def _try_parse_json(raw: bytes) -> dict | None:
    """尝试将字节解析为 JSON dict；失败则返回 None"""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        # 非 dict（如 list、string）包装一层
        return {"_data": parsed}
    except Exception:
        # 非 JSON（如 form、binary）
        text = raw.decode("utf-8", errors="replace")
        return {"_raw": text[:512]} if text.strip() else None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """结构化请求访问日志中间件，记录请求体、响应码、响应体，同时写审计日志"""

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

        # ── 读取请求体（需缓存，否则下游读取为空）────────────────────────
        request_body_raw = await request.body()
        request_body = _desensitize(_try_parse_json(request_body_raw))

        # 将请求体重新注入 scope，让下游路由还能读到
        async def receive() -> Message:
            return {"type": "http.request", "body": request_body_raw, "more_body": False}

        request = Request(request.scope, receive)

        start = time.perf_counter()
        status_code = 500
        response_body: dict | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # ── 消费响应体 ────────────────────────────────────────────────
            resp_chunks: list[bytes] = []
            async for chunk in response.body_iterator:
                resp_chunks.append(chunk)
            resp_raw = b"".join(resp_chunks)

            # 超过上限截断（仅截日志用，响应正常返回）
            # 跳过二进制响应（文件下载等），响应体无审计价值且可能包含特殊字符
            media_type = response.media_type or ""
            if media_type.startswith(("application/octet-stream", "application/zip", "image/", "audio/", "video/")):
                response_body = None
            elif len(resp_raw) <= _RESPONSE_BODY_MAX_BYTES:
                response_body = _desensitize(_try_parse_json(resp_raw))
            else:
                response_body = {"_truncated": True, "_size_bytes": len(resp_raw)}

            # 重新构造响应，保证客户端收到完整数据
            from starlette.responses import Response as StarletteResponse
            response_headers = dict(response.headers)
            response_headers.pop("Content-Length", None)
            response = StarletteResponse(
                content=resp_raw,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.media_type,
            )

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
                query=request.url.query or None,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                client_ip=request_ip,
                user_agent=user_agent,
            )

            if path not in _SKIP_AUDIT_PATHS:
                # TODO: 当前用 create_task 异步写入，进程突然退出时极端情况下可能丢失最后几条日志。
                #       如需 100% 不丢，可引入消息队列（Redis Stream / Kafka）：
                #       中间件将日志事件 push 到队列，独立 consumer 消费写库，
                #       支持重试、持久化，彻底解耦日志写入与业务链路。
                asyncio.create_task(self._record_audit_log(
                    request, path, method, status_code,
                    request_ip, user_agent,
                    request_body=request_body,
                    response_body=response_body,
                ))

    async def _record_audit_log(
        self,
        request: Request,
        path: str,
        method: str,
        status_code: int,
        request_ip: str | None = None,
        user_agent: str | None = None,
        request_body: dict | None = None,
        response_body: dict | None = None,
    ) -> None:
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
                except Exception as e:
                    logger.debug("log_token_parse_failed", error=str(e))

        event_type = f"{method.lower()}.{path.replace('/', '.').strip('.')}"
        if len(event_type) > 64:
            event_type = event_type[:61] + "..."

        parts = path.strip("/").split("/")
        module = parts[1] if len(parts) >= 2 and parts[0] == "api" else None
        resource_type = parts[2] if len(parts) >= 3 and parts[0] == "api" else None

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
            status_code=status_code,
            error_msg=error_msg,
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            request_ip=request_ip,
            user_agent=user_agent,
            browser=browser,
            os_name=os_name,
            device=device,
            trace_id=trace_id,
            path=path,
            method=method,
            request_body=request_body,
            response_body=response_body,
        )

    async def _write_audit_log(
        self,
        event_type: str,
        module: str | None,
        action: str | None,
        resource_type: str | None,
        resource_id: str | None,
        status: int,
        status_code: int,
        error_msg: str | None,
        user_id: int | None = None,
        username: str | None = None,
        tenant_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        browser: str | None = None,
        os_name: str | None = None,
        device: str | None = None,
        trace_id: str | None = None,
        path: str | None = None,
        method: str | None = None,
        request_body: dict | None = None,
        response_body: dict | None = None,
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
                    status_code=status_code,
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
                    request_body=request_body,
                    response_body=response_body,
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
            device = 'Mobile' if ('mobile' in ua or 'phone' in ua) else 'Tablet'
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
        """
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            return True

        if method == "GET":
            path_lower = path.lower()
            for keyword in _EXPORT_KEYWORDS:
                if keyword in path_lower:
                    return True

            parts = path.strip("/").split("/")
            if any(part.isdigit() for part in parts):
                return True

            if resource_type and resource_type in _SENSITIVE_RESOURCES:
                return True

        return False
