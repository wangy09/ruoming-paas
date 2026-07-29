"""
若茗 PaaS - 认证服务单元测试
Author: ruoming
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.core.exceptions import (
    AccountLockedException,
    RefreshTokenInvalidException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.user.models import SysUser


class TestPasswordHashing:
    """密码哈希测试"""

    def test_verify_correct_password(self):
        """正确密码验证通过"""
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """错误密码验证失败"""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_empty_password(self):
        """空密码验证"""
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_hash_deterministic(self):
        """相同密码每次哈希不同（加盐）"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2


class TestTokenGeneration:
    """Token 生成与验证测试"""

    def test_access_token_creation(self):
        """Access Token 创建"""
        user_id = 1
        tenant_id = 1
        token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            is_superplatform=False,
            extra={"username": "testuser"},
        )
        assert token is not None
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["tid"] == tenant_id
        assert payload["sup"] is False
        assert payload["username"] == "testuser"

    def test_refresh_token_creation(self):
        """Refresh Token 创建"""
        user_id = 1
        token, jti = create_refresh_token(user_id)
        assert token is not None
        assert jti is not None
        payload = decode_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["jti"] == jti

    def test_refresh_token_unique(self):
        """每次生成的 Refresh Token 唯一"""
        user_id = 1
        tokens = {create_refresh_token(user_id)[1] for _ in range(10)}
        assert len(tokens) == 10, "所有 Refresh Token 的 JTI 应唯一"


class TestAPIKeyHashing:
    """API Key 哈希测试"""

    def test_hash_consistency(self):
        """相同 Key 哈希结果一致"""
        api_key = "sk_rm_test_key_12345"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)
        assert hash1 == hash2

    def test_hash_uniqueness(self):
        """不同 Key 哈希结果不同"""
        hash1 = hash_api_key("key1")
        hash2 = hash_api_key("key2")
        assert hash1 != hash2

    def test_hash_length(self):
        """哈希长度为 64 位（SHA256）"""
        api_key = "test_key"
        hashed = hash_api_key(api_key)
        assert len(hashed) == 64


class TestAuthServiceLogin:
    """认证服务登录测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库 Session"""
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        """模拟 Redis"""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest_asyncio.fixture
    async def auth_service(self, mock_db, mock_redis):
        """认证服务实例"""
        return AuthService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_service, mock_db):
        """登录不存在的用户应抛出异常"""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        req = LoginRequest(username="nonexistent", password="password")
        with pytest.raises(Exception):
            await auth_service.login(req)

    @pytest.mark.asyncio
    async def test_login_disabled_user(self, auth_service, mock_db):
        """登录已禁用用户应抛出异常"""
        mock_user = MagicMock(spec=SysUser)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.password = hash_password("password")
        mock_user.status = False
        mock_user.is_superplatform = False
        mock_user.tenant_id = 1
        mock_user.nickname = "Test User"
        mock_user.locked_until = None
        mock_user.login_fail_count = 0

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        req = LoginRequest(username="testuser", password="password")
        with pytest.raises(Exception) as exc_info:
            await auth_service.login(req)
        assert exc_info.value.http_status == 403

    @pytest.mark.asyncio
    async def test_login_locked_user(self, auth_service, mock_db):
        """登录已锁定用户应抛出异常"""
        mock_user = MagicMock(spec=SysUser)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.password = hash_password("password")
        mock_user.status = True
        mock_user.is_superplatform = False
        mock_user.tenant_id = 1
        mock_user.nickname = "Test User"
        mock_user.locked_until = datetime.now(UTC) + timedelta(hours=1)
        mock_user.login_fail_count = 3

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        req = LoginRequest(username="testuser", password="password")
        with pytest.raises(AccountLockedException):
            await auth_service.login(req)


class TestRefreshTokenRotation:
    """Refresh Token 轮换测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest_asyncio.fixture
    async def auth_service(self, mock_db, mock_redis):
        return AuthService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_refresh_with_valid_token(self, auth_service, mock_db, mock_redis):
        """使用有效 Refresh Token 成功刷新"""
        user_id = 1
        refresh_token, jti = create_refresh_token(user_id)

        mock_redis.get = AsyncMock(return_value=str(user_id))

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.tenant_id = 1
        mock_user.is_superplatform = False
        mock_user.status = True

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await auth_service.refresh_token(refresh_token)
        assert response.access_token is not None
        assert response.refresh_token is not None
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_with_reused_token(self, auth_service, mock_redis):
        """重放攻击检测"""
        user_id = 1
        refresh_token, jti = create_refresh_token(user_id)

        mock_redis.get = AsyncMock(return_value=None)

        with pytest.raises(RefreshTokenInvalidException):
            await auth_service.refresh_token(refresh_token)

    @pytest.mark.asyncio
    async def test_logout_single_device(self, auth_service, mock_redis):
        """单设备登出"""
        refresh_token, _ = create_refresh_token(1)
        await auth_service.logout(1, refresh_token=refresh_token)
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_all_devices(self, auth_service, mock_redis):
        """所有设备登出"""
        mock_redis.scan = AsyncMock(return_value=(0, ["auth:refresh:key1"]))
        mock_redis.get = AsyncMock(return_value="1")
        await auth_service.logout(1)
        assert mock_redis.delete.call_count >= 1
