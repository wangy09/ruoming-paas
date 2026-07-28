"""
若茗 PaaS - 类型化异常体系
所有业务异常继承 AppException，由全局异常处理器统一格式化响应
Author: ruoming
"""
from app.core.error_codes import SysErrCode


class AppException(Exception):
    """应用级异常基类"""

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        data: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)


class AuthException(AppException):
    """认证异常 - 未登录或 Token 无效"""

    def __init__(
        self,
        message: str = "未登录或 Token 无效",
        code: int = SysErrCode.UNAUTHORIZED,
    ) -> None:
        super().__init__(code=code, message=message, http_status=401)


class TokenExpiredException(AppException):
    """Access Token 过期"""

    def __init__(self) -> None:
        super().__init__(
            code=SysErrCode.TOKEN_EXPIRED,
            message="Token 已过期，请使用 Refresh Token 刷新",
            http_status=401,
        )


class RefreshTokenInvalidException(AppException):
    """Refresh Token 无效或已被轮换消耗"""

    def __init__(self) -> None:
        super().__init__(
            code=SysErrCode.REFRESH_INVALID,
            message="Refresh Token 无效或已过期，请重新登录",
            http_status=401,
        )


class PermissionException(AppException):
    """权限不足"""

    def __init__(self, message: str = "无操作权限") -> None:
        super().__init__(
            code=SysErrCode.FORBIDDEN,
            message=message,
            http_status=403,
        )


class AccountLockedException(AppException):
    """账号被锁定"""

    def __init__(self, message: str = "账号已被锁定，请稍后再试") -> None:
        super().__init__(
            code=SysErrCode.ACCOUNT_LOCKED,
            message=message,
            http_status=403,
        )


class TenantDisabledException(AppException):
    """租户已过期或被禁用"""

    def __init__(self, message: str = "租户已过期或被禁用，请联系管理员") -> None:
        super().__init__(
            code=SysErrCode.TENANT_DISABLED,
            message=message,
            http_status=403,
        )


class DemoModeException(AppException):
    """演示模式下禁止修改操作"""

    def __init__(self, message: str = "演示模式下禁止修改操作") -> None:
        super().__init__(
            code=SysErrCode.DEMO_MODE_RESTRICTED,
            message=message,
            http_status=403,
        )


class NotFoundException(AppException):
    """资源不存在"""

    def __init__(self, resource: str = "资源") -> None:
        super().__init__(
            code=SysErrCode.NOT_FOUND,
            message=f"{resource}不存在",
            http_status=404,
        )


class ValidationException(AppException):
    """参数校验失败"""

    def __init__(
        self,
        message: str = "参数校验失败",
        details: list | None = None,
    ) -> None:
        super().__init__(
            code=SysErrCode.VALIDATION_FAIL,
            message=message,
            http_status=422,
            data={"errors": details} if details else None,
        )


class BusinessException(AppException):
    """通用业务异常（非标准错误，需指定业务错误码）"""

    def __init__(self, code: int, message: str, http_status: int = 400) -> None:
        super().__init__(code=code, message=message, http_status=http_status)


class QuotaExceededException(AppException):
    """配额超限"""

    def __init__(
        self,
        message: str = "配额已耗尽",
        code: int = SysErrCode.QUOTA_API,
    ) -> None:
        super().__init__(code=code, message=message, http_status=429)


class RateLimitException(AppException):
    """接口限流"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试") -> None:
        super().__init__(
            code=SysErrCode.RATE_LIMITED,
            message=message,
            http_status=429,
        )


class ServiceUnavailableException(AppException):
    """依赖服务不可用"""

    def __init__(self, service: str = "依赖服务") -> None:
        super().__init__(
            code=SysErrCode.SERVICE_UNAVAIL,
            message=f"{service}暂时不可用，请稍后再试",
            http_status=503,
        )
