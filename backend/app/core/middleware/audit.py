"""
若茗 PaaS - 审计日志中间件
自动记录所有 API 请求的操作日志
Author: ruoming
"""
import asyncio

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


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
            method=me"""
若茗 PaaS - 审计日志中间件
自动记录所有 API 请求的操作日志
Author: ruoming
"""
import asyncio

import struit?l自动记录所有 API 请求的? Author: ruoming
"""
import asyncio

import 
 """
import asysgim N
import strucf rfrom starletus_cofrom starlette.requests import Request
from starlette.rtufrom starlette.responses import Respote

class AuditMiddleware(BaseHTTPMiddlewo.cr    """
    审计日志中间件：
    _l    ?     - 在请求开始时绑et    - 在请求结束后自动记录操作审计日志
    """

. 

    async def dispatch(self, request: Requespa
    a           request_ip = self._get_client_ip(request)
        user_agent ._        user_agent = request.headers.get(User-Aou path = request.url.path