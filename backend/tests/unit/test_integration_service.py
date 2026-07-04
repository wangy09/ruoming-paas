from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.modules.integration.adapters.webhook import WebhookAdapter
from app.modules.integration.schemas import IntegrationConnectionUpdate
from app.modules.integration.service import IntegrationService


class DummyDB:
    async def flush(self) -> None:
        return None


class CaptureScalarDB(DummyDB):
    def __init__(self) -> None:
        self.statement = None

    async def scalar(self, statement):
        self.statement = statement
        return None


def build_service() -> IntegrationService:
    current_user = SimpleNamespace(id=1, is_superplatform=False, tenant_id=1)
    return IntegrationService(DummyDB(), current_user)  # type: ignore[arg-type]


def build_service_with_db(db) -> IntegrationService:
    current_user = SimpleNamespace(id=1, is_superplatform=False, tenant_id=1)
    return IntegrationService(db, current_user)  # type: ignore[arg-type]


def test_webhook_adapter_does_not_require_webhook_url() -> None:
    assert WebhookAdapter.required_secret_fields == []
    assert "webhook_url" in WebhookAdapter.optional_secret_fields


@pytest.mark.asyncio
async def test_update_connection_validates_existing_secret_config_when_secret_not_submitted() -> None:
    service = build_service()
    conn = SimpleNamespace(
        provider="custom",
        encrypted_config=None,
        capabilities=["bot_message"],
        name="old",
        enabled=True,
        is_default=False,
        config={},
        sort=0,
    )
    adapter = SimpleNamespace(
        capabilities=["bot_message"],
        required_secret_fields=["webhook_url"],
    )

    async def get_connection(_connection_id: int):
        return conn

    service.get_connection = get_connection  # type: ignore[method-assign]
    service._get_adapter = lambda provider: adapter  # type: ignore[method-assign]

    with pytest.raises(ValidationException, match="缺少敏感配置: webhook_url"):
        await service.update_connection(1, IntegrationConnectionUpdate(name="new"))


@pytest.mark.asyncio
async def test_resolve_default_connection_uses_stable_ordering() -> None:
    db = CaptureScalarDB()
    service = build_service_with_db(db)

    with pytest.raises(NotFoundException):
        await service._resolve_connection(None, "feishu")

    assert db.statement is not None
    sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY sys_integration_connection.sort, sys_integration_connection.created_at" in sql
