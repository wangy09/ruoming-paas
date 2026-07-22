"""
若茗 PaaS - JWT 工具、密码哈希、Token 轮换
Author: ruoming
"""
import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.config import settings
from app.core.exceptions import AuthException, TokenExpiredException


def hash_password(plain: str) -> str:
    """bcrypt 单向哈希密码"""
    cost_factor = settings.BCRYPT_COST_FACTOR if hasattr(settings, "BCRYPT_COST_FACTOR") else 12
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=cost_factor)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(
    user_id: int,
    *,
    tenant_id: int | None = None,
    is_superplatform: bool = False,
    extra: dict | None = None,
) -> str:
    """
    生成 Access Token（短期，15 分钟）

    Payload 字段：
        sub  - 用户 ID（字符串）
        tid  - 租户 ID
        sup  - 是否平台超管
        jti  - Token 唯一 ID（防重放）
        exp  - 过期时间
        iat  - 签发时间
        typ  - token 类型
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict = {
        "sub": str(user_id),
        "tid": tenant_id,
        "sup": is_superplatform,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
        "typ": "access",
        **(extra or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """
    生成 Refresh Token（长期，7 天）
    返回 (token, jti)，jti 存入 Redis 用于 Rotation 轮换校验
    """
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": expire,
        "typ": "refresh",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_access_token(token: str) -> dict:
    """
    解码并校验 Access Token。
    抛出 TokenExpiredException 或 AuthException。
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("typ") != "access":
            raise AuthException("Token 类型错误")
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException()
    except jwt.InvalidTokenError as e:
        raise AuthException(f"Token 无效: {e}")


def decode_refresh_token(token: str) -> dict:
    """解码并校验 Refresh Token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("typ") != "refresh":
            raise AuthException("Token 类型错误")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthException("Refresh Token 已过期，请重新登录")
    except jwt.InvalidTokenError as e:
        raise AuthException(f"Refresh Token 无效: {e}")


def decode_token_without_verify(token: str) -> dict:
    """
    不校验签名直接解码 Token（仅在中间件层获取租户 ID 时使用）
    ⚠️ 不可用于权限校验！
    """
    try:
        return jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[settings.JWT_ALGORITHM],
        )
    except Exception:
        return {}


# ── API Key ───────────────────────────────────────────────────────────────────
def generate_api_key() -> tuple[str, str]:
    """
    生成 API Key。
    返回 (raw_key, hashed_key)：raw_key 展示给用户，hashed_key 存数据库。
    格式：rm_{32位随机字符}
    """
    raw = "rm_" + secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_api_key(raw_key: str) -> str:
    """对 API Key 进行 SHA-256 哈希（查找时使用）"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── AES-256 加解密（敏感配置存储）───────────────────────────────────────────
def _get_fernet() -> Fernet:
    """从 ENCRYPT_KEY 初始化 Fernet 实例"""
    key_bytes = settings.ENCRYPT_KEY.encode()
    # Fernet 要求 32 字节 URL-safe base64 密钥
    key = base64.urlsafe_b64encode(key_bytes[:32].ljust(32, b"0"))
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    """AES-256 加密（用于敏感配置存储）"""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """AES-256 解密"""
    return _get_fernet().decrypt(encrypted.encode()).decode()
