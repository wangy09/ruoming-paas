"""
若茗 PaaS - 敏感数据脱敏工具

用于日志输出、API 响应中的敏感字段自动脱敏。
支持：手机号、邮箱、身份证、密码、Token、银行卡号等。

Author: ruoming
"""
from __future__ import annotations

import re
from typing import Any

# ── 敏感字段名称（大小写不敏感） ──────────────────────────────────
SENSITIVE_FIELD_NAMES = {
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "authorization",
    "api_key", "apikey", "secret", "secret_key", "app_secret",
    "credit_card", "card_number", "bank_card",
    "id_card", "idcard", "id_number",
    "phone", "mobile", "mobile_number", "phone_number",
    "email", "e_mail",
    "address", "home_address",
    "salary", "income", "bank_account",
    "password_hash", "passwd_hash",
    "captcha", "captcha_code",
    "verification_code", "sms_code",
}

# ── 脱敏规则 ──────────────────────────────────────────────────────
def mask_phone(value: str) -> str:
    """手机号脱敏：138****8888"""
    if not value or len(value) < 7:
        return value
    return value[:3] + "****" + value[-4:]


def mask_email(value: str) -> str:
    """邮箱脱敏：x****@example.com"""
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        return f"{local[0]}****@{domain}"
    return f"{local[0]}****{local[-1]}@{domain}"


def mask_id_card(value: str) -> str:
    """身份证脱敏：310***********1234"""
    if not value or len(value) < 8:
        return value
    return value[:3] + "********" + value[-4:]


def mask_bank_card(value: str) -> str:
    """银行卡脱敏：6222********1234"""
    if not value or len(value) < 8:
        return value
    return value[:4] + "**********" + value[-4:]


def mask_token(value: str) -> str:
    """Token 脱敏：截取前 8 位"""
    if not value or len(value) < 10:
        return "****"
    return value[:8] + "..."


def mask_secret(value: str) -> str:
    """密钥脱敏"""
    if not value:
        return "****"
    return "****"


# ── 字段名到脱敏函数的映射 ──────────────────────────────────────
FIELD_MASKERS = {
    "phone": mask_phone,
    "mobile": mask_phone,
    "mobile_number": mask_phone,
    "phone_number": mask_phone,
    "email": mask_email,
    "e_mail": mask_email,
    "id_card": mask_id_card,
    "idcard": mask_id_card,
    "id_number": mask_id_card,
    "credit_card": mask_bank_card,
    "card_number": mask_bank_card,
    "bank_card": mask_bank_card,
    "bank_account": mask_bank_card,
}


def _get_masker(field_name: str):
    """根据字段名获取脱敏函数"""
    name_lower = field_name.lower().replace("_", "")
    for key, masker in FIELD_MASKERS.items():
        if key.replace("_", "") in name_lower:
            return masker
    if any(s in name_lower for s in ("password", "token", "secret", "api_key", "apikey", "authorization", "captcha", "code")):
        return mask_secret
    return None


def is_sensitive_field(field_name: str) -> bool:
    """判断字段是否为敏感字段"""
    return field_name.lower() in SENSITIVE_FIELD_NAMES or _get_masker(field_name) is not None


def mask_value(field_name: str, value: Any) -> Any:
    """
    脱敏单个字段值。

    Args:
        field_name: 字段名
        value: 字段值

    Returns:
        脱敏后的值
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    masker = _get_masker(field_name)
    if masker:
        return masker(value)
    if field_name.lower() in SENSITIVE_FIELD_NAMES:
        return mask_secret(value)
    return value


def mask_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    递归脱敏字典中的敏感字段。

    Args:
        data: 原始字典

    Returns:
        脱敏后的字典
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = mask_dict(value)
        elif isinstance(value, list):
            result[key] = mask_list(value)
        elif isinstance(value, str):
            result[key] = mask_value(key, value)
        else:
            result[key] = value
    return result


def mask_list(data: list[Any]) -> list[Any]:
    """脱敏列表中的敏感数据"""
    return [
        mask_dict(item) if isinstance(item, dict)
        else mask_list(item) if isinstance(item, list)
        else item
        for item in data
    ]


def mask_log_message(message: str, extra: dict[str, Any] | None = None) -> str:
    """
    脱敏日志消息中的敏感信息。

    Args:
        message: 日志消息
        extra: 额外数据（会被脱敏）

    Returns:
        脱敏后的日志消息
    """
    sensitive_patterns = [
        (r'(password|passwd|pwd)\s*[=:]\s*["\']?\S+', r'\1=****'),
        (r'(token|access_token|refresh_token)\s*[=:]\s*["\']?\S+', r'\1=****'),
        (r'(authorization)\s*[=:]\s*["\']?\S+', r'\1=****'),
        (r'(api_key|apikey|secret_key)\s*[=:]\s*["\']?\S+', r'\1=****'),
        (r'(captcha|code)\s*[=:]\s*["\']?\S+', r'\1=****'),
    ]

    result = message
    for pattern, replacement in sensitive_patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


class SensitiveDataFilter:
    """
    structlog 敏感数据过滤器。

    用法：
        import structlog
        from app.core.sensitive_mask import SensitiveDataFilter

        filter = SensitiveDataFilter()
        logger = structlog.get_logger()
        logger = logger.bind(sensitive_filter=filter)

        # 在处理器中使用
        def filter_sensitive(logger, method_name, event_dict):
            return filter.filter_event(event_dict)
    """

    def __init__(self) -> None:
        self.sensitive_keys = SENSITIVE_FIELD_NAMES

    def filter_event(self, event_dict: dict[str, Any]) -> dict[str, Any]:
        """过滤日志事件中的敏感字段"""
        return mask_dict(event_dict)


def create_structlog_processor():
    """
    创建 structlog 处理器，用于在日志输出时自动脱敏。

    用法：
        processor = create_structlog_processor()
        structlog.configure(
            processors=[processor, structlog.ConsoleRenderer()],
        )
    """
    def processor(logger, method_name, event_dict):
        return mask_dict(event_dict)
    return processor
