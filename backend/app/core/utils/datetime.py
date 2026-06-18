"""
若茗 PaaS - 时间工具函数
Author: ruoming
"""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """返回当前 UTC 时间（timezone-aware）"""
    return datetime.now(UTC)


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str | None:
    """格式化时间"""
    if dt is None:
        return None
    return dt.strftime(fmt)


def is_expired(dt: datetime | None) -> bool:
    """检查时间是否已过期"""
    if dt is None:
        return False
    return datetime.now(UTC) > dt
