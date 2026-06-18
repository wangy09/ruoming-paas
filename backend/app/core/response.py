"""
若茗 PaaS - 统一响应格式
Author: ruoming
"""
import math
from typing import Any, Generic, TypeVar

import structlog
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应体"""

    code: int = 200
    message: str = "success"
    data: T | None = None
    trace_id: str | None = None


class PageData(BaseModel, Generic[T]):
    """分页数据容器"""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
    has_more: bool


def ok(data: Any = None, message: str = "success") -> ApiResponse:
    """成功响应"""
    trace_id = _get_trace_id()
    return ApiResponse(code=200, message=message, data=data, trace_id=trace_id)


def created(data: Any = None, message: str = "创建成功") -> ApiResponse:
    """创建成功响应"""
    trace_id = _get_trace_id()
    return ApiResponse(code=201, message=message, data=data, trace_id=trace_id)


def paged(
    items: list,
    total: int,
    page: int,
    page_size: int,
) -> ApiResponse[PageData]:
    """分页响应"""
    pages = math.ceil(total / page_size) if page_size else 0
    trace_id = _get_trace_id()
    return ApiResponse(
        code=200,
        message="success",
        data=PageData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_more=page < pages,
        ),
        trace_id=trace_id,
    )


def error(code: int, message: str, data: Any = None) -> ApiResponse:
    """错误响应"""
    trace_id = _get_trace_id()
    return ApiResponse(code=code, message=message, data=data, trace_id=trace_id)


def _get_trace_id() -> str | None:
    """从 structlog 上下文变量中获取 trace_id"""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("trace_id") or ctx.get("request_id")
    except Exception:
        return None
