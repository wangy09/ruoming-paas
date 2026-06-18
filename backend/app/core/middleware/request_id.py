"""
若茗 PaaS - RequestID 中间件
为每个请求注入唯一 trace_id，贯穿全链路日志
Author: ruoming
"""
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    为每个请求生成唯一 trace_id：
    - 优先使用客户端传入的 X-Request-ID（方便调用方追踪）
    - 否则自动生成 UUID4
    - 绑定到 structlog 上下文变量，全链路日志自动携带
    - 响应头回传 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 获取或生成 trace_id
        trace_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Trace-ID")
            or str(uuid.uuid4())
        )

        # 绑定到 structlog 上下文（线程/协程安全）
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        # 注入 request.state 方便其他地方使用
        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
