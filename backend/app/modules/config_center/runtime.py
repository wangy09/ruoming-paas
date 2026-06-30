"""
运行时配置读取工具。

业务代码通过这里读取配置中心，并保留 settings/.env 作为兜底。
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.config_center.service import ConfigCenterService

logger = structlog.get_logger(__name__)


async def get_runtime_config(
    db: AsyncSession,
    keys: list[str],
    *,
    tenant_id: int | None = None,
    app_key: str | None = None,
    user_id: int | None = None,
) -> dict[str, str]:
    """读取配置中心运行时配置；失败时返回空字典，不阻断业务主流程。"""
    try:
        return await ConfigCenterService(db).get_merged(
            keys=keys,
            tenant_id=tenant_id,
            app_key=app_key,
            user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("runtime_config_load_failed", keys=keys, error=str(exc))
        return {}


def cfg_int(values: dict[str, str], key: str, default: int, *, min_value: int | None = None) -> int:
    try:
        value = int(values.get(key, default))
    except (TypeError, ValueError):
        value = default
    if min_value is not None:
        return max(value, min_value)
    return value


def cfg_float(values: dict[str, str], key: str, default: float) -> float:
    try:
        return float(values.get(key, default))
    except (TypeError, ValueError):
        return default


def cfg_bool(values: dict[str, str], key: str, default: bool) -> bool:
    raw = values.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def cfg_list(values: dict[str, str], key: str, default: list[str]) -> list[str]:
    raw = values.get(key)
    if raw is None or raw == "":
        return default
    try:
        parsed: Any = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]
