"""
若茗 PaaS - 配置中心服务单元测试
Author: ruoming
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.modules.config_center.service import ConfigCenterService, _merged_cache_key


class TestCacheKeyGeneration:
    """缓存 Key 生成测试"""

    def test_cache_key_consistency(self):
        """相同参数生成相同 Key"""
        key1 = _merged_cache_key(["key1", "key2"], 1, "app", 1, False)
        key2 = _merged_cache_key(["key1", "key2"], 1, "app", 1, False)
        assert key1 == key2

    def test_cache_key_order_independent(self):
        """Key 顺序不影响结果"""
        key1 = _merged_cache_key(["key1", "key2"], 1, None, None, False)
        key2 = _merged_cache_key(["key2", "key1"], 1, None, None, False)
        assert key1 == key2

    def test_cache_key_different_params(self):
        """不同参数生成不同 Key"""
        key1 = _merged_cache_key(["key1"], 1, None, None, False)
        key2 = _merged_cache_key(["key1"], 2, None, None, False)
        assert key1 != key2

    def test_cache_key_public_flag(self):
        """public_only 标志影响 Key"""
        key1 = _merged_cache_key(["key1"], 1, None, None, False)
        key2 = _merged_cache_key(["key1"], 1, None, None, True)
        assert key1 != key2


class TestConfigValueValidation:
    """配置值校验测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest_asyncio.fixture
    async def config_service(self, mock_db):
        return ConfigCenterService(mock_db)

    @pytest.mark.asyncio
    async def test_validate_required_empty(self, config_service):
        """必填配置空值校验"""
        from app.core.exceptions import ValidationException
        with pytest.raises(ValidationException, match="配置值不能为空"):
            config_service._validate_config_value(
                "",
                val_type="string",
                required=True,
                regex=None,
                min_value=None,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_json_format(self, config_service):
        """JSON 格式校验"""
        from app.core.exceptions import ValidationException
        with pytest.raises(ValidationException, match="JSON 格式不正确"):
            config_service._validate_config_value(
                "invalid_json",
                val_type="json",
                required=False,
                regex=None,
                min_value=None,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_json_valid(self, config_service):
        """有效 JSON 通过校验"""
        config_service._validate_config_value(
            '{"key": "value"}',
            val_type="json",
            required=False,
            regex=None,
            min_value=None,
            max_value=None,
        )

    @pytest.mark.asyncio
    async def test_validate_int_range(self, config_service):
        """整数范围校验"""
        from app.core.exceptions import ValidationException
        with pytest.raises(ValidationException, match="配置值不能小于"):
            config_service._validate_config_value(
                "5",
                val_type="int",
                required=False,
                regex=None,
                min_value=10,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_bool_invalid(self, config_service):
        """布尔值校验"""
        from app.core.exceptions import ValidationException
        with pytest.raises(ValidationException, match="布尔配置值必须是"):
            config_service._validate_config_value(
                "invalid",
                val_type="bool",
                required=False,
                regex=None,
                min_value=None,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_bool_valid(self, config_service):
        """有效布尔值通过"""
        for val in ["true", "false", "1", "0", "yes", "no", "on", "off"]:
            config_service._validate_config_value(
                val,
                val_type="bool",
                required=False,
                regex=None,
                min_value=None,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_regex(self, config_service):
        """正则校验"""
        from app.core.exceptions import ValidationException
        with pytest.raises(ValidationException, match="不符合正则"):
            config_service._validate_config_value(
                "invalid_email",
                val_type="string",
                required=False,
                regex=r"^[\w.-]+@[\w.-]+\.\w+$",
                min_value=None,
                max_value=None,
            )

    @pytest.mark.asyncio
    async def test_validate_skip_empty(self, config_service):
        """跳过空值校验"""
        config_service._validate_config_value(
            "",
            val_type="string",
            required=True,
            regex=None,
            min_value=None,
            max_value=None,
            skip_empty=True,
        )


class TestTypeConversion:
    """类型转换辅助测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest_asyncio.fixture
    async def config_service(self, mock_db):
        return ConfigCenterService(mock_db)

    @pytest.mark.asyncio
    async def test_get_bool_true_values(self, config_service):
        """布尔真值转换"""
        for val in ["true", "1", "yes", "on", "TRUE", "True"]:
            assert config_service.get_bool(val) is True

    @pytest.mark.asyncio
    async def test_get_bool_false_values(self, config_service):
        """布尔假值转换"""
        for val in ["false", "0", "no", "off", "FALSE", None]:
            assert config_service.get_bool(val) is False

    @pytest.mark.asyncio
    async def test_get_int_valid(self, config_service):
        """整数转换"""
        assert config_service.get_int("123") == 123
        assert config_service.get_int("-456") == -456

    @pytest.mark.asyncio
    async def test_get_int_invalid(self, config_service):
        """无效整数返回默认值"""
        assert config_service.get_int("abc", default=0) == 0
        assert config_service.get_int(None, default=10) == 10

    @pytest.mark.asyncio
    async def test_get_json_valid(self, config_service):
        """有效 JSON 转换"""
        result = config_service.get_json('{"key": "value"}')
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_json_invalid(self, config_service):
        """无效 JSON 返回默认值"""
        result = config_service.get_json("invalid", default={})
        assert result == {}


class TestOutputFormat:
    """输出格式测试"""

    @pytest.mark.asyncio
    async def test_to_output_normal(self):
        """普通配置输出"""
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.scope = "global"
        mock_row.config_key = "test.key"
        mock_row.config_val = "test_value"
        mock_row.is_encrypted = False
        mock_row.val_type = "string"
        mock_row.category = "test"
        mock_row.config_type = "input"
        mock_row.default_value = "default"
        mock_row.options = None
        mock_row.required = False
        mock_row.regex = None
        mock_row.min_value = None
        mock_row.max_value = None
        mock_row.sort = 0
        mock_row.status = 1
        mock_row.label = "Test Config"
        mock_row.description = "Test description"
        mock_row.is_public = False
        mock_row.app_key = None
        mock_row.user_id = None
        mock_row.tenant_id = None

        output = ConfigCenterService.to_output(mock_row)
        assert output["config_val"] == "test_value"
        assert output["display_val"] == "test_value"
        assert output["is_encrypted"] is False

    @pytest.mark.asyncio
    async def test_to_output_encrypted(self):
        """加密配置输出"""
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.scope = "global"
        mock_row.config_key = "secret.key"
        mock_row.config_val = "encrypted_value"
        mock_row.is_encrypted = True
        mock_row.val_type = "string"
        mock_row.category = "security"
        mock_row.config_type = "password"
        mock_row.default_value = None
        mock_row.options = None
        mock_row.required = True
        mock_row.regex = None
        mock_row.min_value = None
        mock_row.max_value = None
        mock_row.sort = 0
        mock_row.status = 1
        mock_row.label = "Secret"
        mock_row.description = "Secret config"
        mock_row.is_public = False
        mock_row.app_key = None
        mock_row.user_id = None
        mock_row.tenant_id = None

        output = ConfigCenterService.to_output(mock_row)
        assert output["config_val"] is None
        assert output["display_val"] == "******"
        assert output["is_encrypted"] is True


class TestScopeQuery:
    """层级查询构建测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest_asyncio.fixture
    async def config_service(self, mock_db):
        return ConfigCenterService(mock_db)

    @pytest.mark.asyncio
    async def test_build_global_scope_stmt(self, config_service):
        """global 层级查询"""
        stmt = config_service._build_scope_stmt(
            "global", ["key1", "key2"], None, None, None
        )
        assert stmt is not None

    @pytest.mark.asyncio
    async def test_build_tenant_scope_stmt(self, config_service):
        """tenant 层级查询"""
        stmt = config_service._build_scope_stmt(
            "tenant", ["key1"], 1, None, None
        )
        assert stmt is not None

    @pytest.mark.asyncio
    async def test_build_app_scope_stmt(self, config_service):
        """app 层级查询"""
        stmt = config_service._build_scope_stmt(
            "app", ["key1"], 1, "myapp", None
        )
        assert stmt is not None

    @pytest.mark.asyncio
    async def test_build_user_scope_stmt(self, config_service):
        """user 层级查询"""
        stmt = config_service._build_scope_stmt(
            "user", ["key1"], 1, None, 100
        )
        assert stmt is not None
