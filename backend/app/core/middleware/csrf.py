import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

CSRF_EXEMPT_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/health",
    "/api/v1/auth/captcha",
]

CSRF_COOKIE_SECURE = not settings.is_development

# Bearer Token 认证的请求豁免 CSRF 检查
# 原因：Bearer Token 不会被浏览器自动附加（不同于 Cookie），
# 纯 API 客户端（移动端、第三方集成、CLI 工具）无法获取 csrf_token，
# 强制检查会导致 403。这是业界标准做法（DRF、OWASP 均推荐）。
_BEARER_SCHEME = "Bearer"


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        csrf_cookie = request.cookies.get("csrf_token")

        if not csrf_cookie:
            csrf_cookie = secrets.token_hex(32)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            self._set_csrf_cookie(response, csrf_cookie)
            return response

        if any(request.url.path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            response = await call_next(request)
            self._set_csrf_cookie(response, csrf_cookie)
            return response

        # Bearer Token 请求豁免：Authorization: Bearer xxx
        # Bearer Token 不会被浏览器自动附加，不存在 CSRF 攻击面
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith(_BEARER_SCHEME):
            response = await call_next(request)
            self._set_csrf_cookie(response, csrf_cookie)
            return response

        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or csrf_cookie != csrf_header:
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "CSRF 验证失败"}
            )

        response = await call_next(request)
        self._set_csrf_cookie(response, csrf_cookie)
        return response

    @staticmethod
    def _set_csrf_cookie(response: Response, value: str) -> None:
        response.set_cookie(
            key="csrf_token",
            value=value,
            httponly=False,
            secure=CSRF_COOKIE_SECURE,
            samesite="lax",
        )
