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

_RUNTIME_CONFIGS = [
    {
        "config_key": "site.title",
        "config_val": "若茗 PaaS",
        "val_type": "string",
        "category": "site",
        "config_type": "input",
        "label": "系统名称",
        "description": "浏览器标题、后台 Logo 文案、登录页标题",
        "is_public": True,
        "sort": 10,
    },
    {
        "config_key": "site.login_subtitle",
        "config_val": "企业级 AI 应用开发底座",
        "val_type": "string",
        "category": "site",
        "config_type": "input",
        "label": "登录页副标题",
        "is_public": True,
        "sort": 20,
    },
    {
        "config_key": "site.logo_url",
        "config_val": "/logo.svg",
        "val_type": "string",
        "category": "site",
        "config_type": "input",
        "label": "Logo 地址",
        "is_public": True,
        "sort": 30,
    },
    {
        "config_key": "ui.primary_color",
        "config_val": "#1677ff",
        "val_type": "string",
        "category": "ui",
        "config_type": "input",
        "label": "主题色",
        "regex": r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        "is_public": True,
        "sort": 40,
    },
    {
        "config_key": "multi_tenant.enabled",
        "config_val": "true",
        "val_type": "bool",
        "category": "system",
        "config_type": "switch",
        "label": "多租户模式",
        "description": "开启后系统启用多租户隔离，关闭后所有用户共享同一数据空间",
        "is_public": False,
        "sort": 999,
    },
    {
        "config_key": "rate_limit.enabled",
        "config_val": "true",
        "val_type": "bool",
        "category": "rate_limit",
        "config_type": "switch",
        "label": "限流开关",
        "description": "开启后启用系统限流保护，关闭后所有限流规则失效",
        "is_public": False,
        "sort": 1,
    },
    {
        "config_key": "rate_limit.global.default",
        "config_val": "100/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "全局默认限流",
        "description": "所有接口的默认限流规则，格式：数字/单位（如 100/minute）",
        "is_public": False,
        "sort": 2,
    },
    {
        "config_key": "rate_limit.ip.default",
        "config_val": "300/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "IP 级限流",
        "description": "按 IP 地址的限流规则，防 DDoS 和爆破",
        "is_public": False,
        "sort": 3,
    },
    {
        "config_key": "rate_limit.user.default",
        "config_val": "60/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "用户级限流",
        "description": "按用户 ID 的限流规则，防单用户过度消耗",
        "is_public": False,
        "sort": 4,
    },
    {
        "config_key": "rate_limit.tenant.default",
        "config_val": "500/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "租户级限流",
        "description": "按租户 ID 的限流规则，防单租户拖垮系统",
        "is_public": False,
        "sort": 5,
    },
    {
        "config_key": "rate_limit.api.login",
        "config_val": "10/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "登录接口限流",
        "description": "登录接口的限流规则，更严格以防止暴力破解",
        "is_public": False,
        "sort": 6,
    },
    {
        "config_key": "rate_limit.api.register",
        "config_val": "5/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "注册接口限流",
        "description": "注册接口的限流规则",
        "is_public": False,
        "sort": 7,
    },
    {
        "config_key": "rate_limit.api.captcha",
        "config_val": "3/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "验证码接口限流",
        "description": "验证码发送接口的限流规则",
        "is_public": False,
        "sort": 8,
    },
    {
        "config_key": "rate_limit.ai.chat",
        "config_val": "30/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "AI 对话限流",
        "description": "AI 对话接口的限流规则",
        "is_public": False,
        "sort": 9,
    },
    {
        "config_key": "rate_limit.ai.agent",
        "config_val": "30/minute",
        "val_type": "string",
        "category": "rate_limit",
        "config_type": "input",
        "label": "AI Agent 限流",
        "description": "AI Agent 执行接口的限流规则",
        "is_public": False,
        "sort": 10,
    },
]


async def ensure_runtime_configs(db: AsyncSession) -> None:
    """确保配置中心运行时配置已初始化（系统启动时调用）"""
    svc = ConfigCenterService(db)
    updated_count = 0

    for item in _RUNTIME_CONFIGS:
        await svc.set(scope="global", status=1, **item)
        updated_count += 1

    await db.commit()
    logger.info("runtime_configs_initialized", count=updated_count)


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
