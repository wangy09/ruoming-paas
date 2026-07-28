from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class DemoModeMiddleware(BaseHTTPMiddleware):
    WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    WHITELIST_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/system/demo-mode",
        "/api/v1/config-center/public",
        "/health",
    }

    WHITELIST_PREFIXES = {
        "/api/v1/auth/",
        "/api/v1/dashboard/",
        "/api/v1/monitor/",
        "/api/v1/audit/",
    }

    async def dispatch(self, request: Request, call_next):
        if not settings.DEMO_MODE:
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path

        if method in self.WRITE_METHODS:
            if self.is_whitelisted(path):
                return await call_next(request)

            return JSONResponse(
                status_code=403,
                content={
                    "code": 10204,
                    "message": "演示模式下禁止修改操作，请登录正式环境使用完整功能",
                    "data": None,
                },
            )

        return await call_next(request)

    def is_whitelisted(self, path: str) -> bool:
        if path in self.WHITELIST_PATHS:
            return True
        for prefix in self.WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return True
        return False