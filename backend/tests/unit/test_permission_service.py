"""
若茗 PaaS - 权限服务单元测试
Author: ruoming
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.modules.permission.service import PermissionService, PERM_CACHE_TTL


def _make_scalar_result(value):
    """模拟 SQLAlchemy ScalarResult"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_scalars_result(items):
    """模拟 SQLAlchemy ScalarsResult (有 .all() 方法)"""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    result.scalar_one_or_none.return_value = None
    return result


class TestPermissionCache:
    """权限缓存测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock()
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest_asyncio.fixture
    async def perm_service(self, mock_db, mock_redis):
        return PermissionService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_get_user_permissions_cache_hit(self, perm_service, mock_redis):
        """缓存命中时直接返回"""
        cached_data = json.dumps({"codes": ["user:view", "user:create"]})
        mock_redis.get = AsyncMock(return_value=cached_data)

        codes = await perm_service.get_user_permission_codes(1)
        assert "user:view" in codes
        assert "user:create" in codes
        assert len(codes) == 2

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, perm_service, mock_redis):
        """使用户缓存失效"""
        await perm_service.invalidate_user_permission_cache(1)
        mock_redis.delete.assert_called_once()


class TestPermissionComputation:
    """权限计算测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest_asyncio.fixture
    async def perm_service(self, mock_db, mock_redis):
        return PermissionService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_compute_permissions_empty_user(self, perm_service, mock_db):
        """无角色用户权限为空"""
        mock_db.execute = AsyncMock(return_value=_make_scalar_result(None))

        codes = await perm_service._compute_user_permissions(999)
        assert len(codes) == 0

    @pytest.mark.asyncio
    async def test_build_menu_tree_empty(self, perm_service):
        """空菜单列表构建"""
        tree = perm_service._build_menu_tree([])
        assert tree == []

    @pytest.mark.asyncio
    async def test_build_menu_tree_flat(self, perm_service):
        """扁平菜单构建"""
        items = [
            {"id": 1, "parent_id": 0, "title": "菜单1", "sort": 1},
            {"id": 2, "parent_id": 0, "title": "菜单2", "sort": 2},
        ]
        tree = perm_service._build_menu_tree(items)
        assert len(tree) == 2
        assert tree[0]["title"] == "菜单1"

    @pytest.mark.asyncio
    async def test_build_menu_tree_nested(self, perm_service):
        """嵌套菜单构建"""
        items = [
            {"id": 1, "parent_id": 0, "title": "父菜单", "sort": 1},
            {"id": 2, "parent_id": 1, "title": "子菜单1", "sort": 1},
            {"id": 3, "parent_id": 1, "title": "子菜单2", "sort": 2},
        ]
        tree = perm_service._build_menu_tree(items)
        assert len(tree) == 1
        assert tree[0]["title"] == "父菜单"
        assert len(tree[0]["children"]) == 2


class TestDataScope:
    """数据权限范围测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest_asyncio.fixture
    async def perm_service(self, mock_db, mock_redis):
        return PermissionService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_superuser_data_scope(self, perm_service, mock_db):
        """超管拥有全部数据权限"""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_superplatform = True
        mock_user.tenant_id = 1

        mock_db.execute = AsyncMock(return_value=_make_scalar_result(mock_user))

        scope = await perm_service.get_user_data_scope_filter(1, None)
        assert scope["data_scope"] == 1
        assert scope["allowed_dept_ids"] is None

    @pytest.mark.asyncio
    async def test_no_role_user_scope(self, perm_service, mock_db):
        """无角色用户默认仅本人"""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_superplatform = False
        mock_user.tenant_id = 1

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_scalar_result(mock_user),
                _make_scalars_result([]),
            ]
        )

        scope = await perm_service.get_user_data_scope_filter(1, None)
        assert scope["data_scope"] == 5


class TestRolePermissionInheritance:
    """角色权限继承测试"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest_asyncio.fixture
    async def perm_service(self, mock_db, mock_redis):
        return PermissionService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_get_nonexistent_role_permissions(self, perm_service, mock_db):
        """获取不存在的角色权限返回空"""
        mock_db.execute = AsyncMock(return_value=_make_scalar_result(None))

        codes = await perm_service.get_role_permission_codes(999)
        assert len(codes) == 0
