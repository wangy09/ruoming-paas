"""
若茗 PaaS - 认证接口集成测试
Author: ruoming
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestLoginAPI:
    async def test_health_check(self, client: AsyncClient):
        """健康检查接口"""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_login_with_invalid_credentials(self, client: AsyncClient):
        """错误密码返回 401"""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "wrongpass"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == 21002

    async def test_login_validation_error(self, client: AsyncClient):
        """缺少必填字段返回 422"""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": ""},
        )
        assert resp.status_code == 422

    async def test_refresh_with_invalid_token(self, client: AsyncClient):
        """无效 Refresh Token 返回 401"""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_me_without_token(self, client: AsyncClient):
        """未携带 Token 访问 /me 返回 401"""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
