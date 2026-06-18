"""
若茗 PaaS - 安全工具单元测试
Author: ruoming
"""
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
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
