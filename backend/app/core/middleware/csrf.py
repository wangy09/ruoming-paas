import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CSRF_EXEMPT_PATHS = ["/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/health"]


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        csrf_cookie = request.cookies.get("csrf_token")

        if not csrf_cookie:
            csrf_cookie = secrets.token_hex(32)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            response.set_cookie(
                key="csrf_token",
                value=csrf_cookie,
                httponly=False,
                secure=True,
                samesite="strict",
            )
            return response

        if any(request.url.path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            response = await call_next(request)
            response.set_cookie(
                key="csrf_token",
                value=csrf_cookie,
                httponly=False,
                secure=True,
                samesite="strict",
            )
            return response

        if request.headers.get("Authorization", "").startswith("Bearer "):
            response = await call_next(request)
            return response

        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or csrf_cookie != csrf_header:
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "CSRF 验证失败"}
            )

        response = await call_next(request)
        return response
