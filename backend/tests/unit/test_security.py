"""
若茗 PaaS - 安全工具单元测试
Author: ruoming
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token_without_verify,
    decrypt_value,
    encrypt_value,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.core.exceptions import TokenExpiredException, AuthException


class TestPasswordHashing:
    def test_hash_password(self):
        hashed = hash_password("test@123")
        assert hashed != "test@123"
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_cost_factor(self):
        with patch("app.core.security.settings.BCRYPT_COST_FACTOR", 12):
            hashed = hash_password("test-password")
            assert hashed.startswith("$2b$12$")

    def test_hash_password_empty_string(self):
        hashed = hash_password("")
        assert hashed.startswith("$2b$")
        assert verify_password("", hashed) is True

    def test_hash_password_special_chars(self):
        hashed = hash_password("test@#$%^&*()_+")
        assert hashed.startswith("$2b$")
        assert verify_password("test@#$%^&*()_+", hashed) is True

    def test_hash_password_unicode(self):
        hashed = hash_password("测试密码")
        assert hashed.startswith("$2b$")
        assert verify_password("测试密码", hashed) is True

    def test_hash_password_consistency(self):
        pwd = "consistent_password_123"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2
        assert verify_password(pwd, h1) is True
        assert verify_password(pwd, h2) is True


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token(user_id=1, tenant_id=1)
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["tid"] == 1
        assert payload["typ"] == "access"

    def test_create_refresh_token(self):
        token, jti = create_refresh_token(user_id=1)
        assert token
        assert len(jti) > 0

    def test_superplatform_token(self):
        token = create_access_token(user_id=1, is_superplatform=True)
        payload = decode_access_token(token)
        assert payload["sup"] is True

    def test_invalid_token_raises(self):
        with pytest.raises(AuthException):
            decode_access_token("invalid.token.here")

    def test_decode_refresh_token(self):
        token, jti = create_refresh_token(user_id=123)
        payload = decode_refresh_token(token)
        assert payload["sub"] == "123"
        assert payload["jti"] == jti
        assert payload["typ"] == "refresh"

    def test_decode_token_without_verify(self):
        token = create_access_token(user_id=1, tenant_id=2)
        payload = decode_token_without_verify(token)
        assert payload["sub"] == "1"
        assert payload["tid"] == 2

    def test_decode_token_without_verify_invalid(self):
        payload = decode_token_without_verify("invalid.token")
        assert payload == {}

    def test_access_token_with_extra_data(self):
        token = create_access_token(user_id=1, extra={"custom": "data", "roles": ["admin"]})
        payload = decode_access_token(token)
        assert payload["custom"] == "data"
        assert payload["roles"] == ["admin"]

    def test_wrong_token_type_access(self):
        refresh_token, _ = create_refresh_token(user_id=1)
        with pytest.raises(AuthException):
            decode_access_token(refresh_token)

    def test_wrong_token_type_refresh(self):
        access_token = create_access_token(user_id=1)
        with pytest.raises(AuthException):
            decode_refresh_token(access_token)


class TestApiKey:
    def test_generate_api_key(self):
        raw, hashed = generate_api_key()
        assert raw.startswith("rm_")
        assert len(raw) > 10
        assert hashed != raw

    def test_hash_api_key_consistent(self):
        raw, _ = generate_api_key()
        h1 = hash_api_key(raw)
        h2 = hash_api_key(raw)
        assert h1 == h2

    def test_api_key_hash_matches(self):
        raw, hashed = generate_api_key()
        assert hash_api_key(raw) == hashed


class TestEncryption:
    def test_encrypt_decrypt(self):
        plain = "sensitive-api-key-value"
        encrypted = encrypt_value(plain)
        assert encrypted != plain
        decrypted = decrypt_value(encrypted)
        assert decrypted == plain

    def test_different_values_different_ciphertexts(self):
        # Fernet 每次加密结果不同（包含随机 IV）
        v1 = encrypt_value("same-value")
        v2 = encrypt_value("same-value")
        assert v1 != v2  # 但解密后相同
        assert decrypt_value(v1) == decrypt_value(v2)
