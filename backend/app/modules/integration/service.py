"""
若茗 PaaS - 第三方协作平台集成服务
"""
import json
from collections.abc import Sequence

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.core.security import decrypt_value, encrypt_value
from app.modules.integration.adapters.base import AdapterContext
from app.modules.integration.models import SysIntegrationConnection
from app.modules.integration.registry import integration_registry
from app.modules.integration.schemas import (
    IntegrationConnectionCreate,
    IntegrationConnectionOut,
    IntegrationConnectionUpdate,
    IntegrationSendMessageRequest,
    IntegrationSendMessageResult,
    IntegrationTestResult,
)
from app.modules.user.models import SysUser


class IntegrationService:
    """第三方协作平台集成服务。"""

    def __init__(self, db: AsyncSession, current_user: SysUser) -> None:
        self.db = db
        self.current_user = current_user
        self.tenant_id = None if current_user.is_superplatform else current_user.tenant_id

    async def list_connections(self, provider: str | None = None, enabled: bool | None = None) -> list[IntegrationConnectionOut]:
        conditions = [SysIntegrationConnection.is_deleted == False]  # noqa: E712
        if self.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == self.tenant_id)
        if provider:
            conditions.append(SysIntegrationConnection.provider == provider)
        if enabled is not None:
            conditions.append(SysIntegrationConnection.enabled == enabled)

        rows = await self.db.execute(
            select(SysIntegrationConnection)
            .where(*conditions)
            .order_by(SysIntegrationConnection.sort, desc(SysIntegrationConnection.created_at))
        )
        return [self.to_output(item) for item in rows.scalars().all()]

    async def create_connection(self, data: IntegrationConnectionCreate) -> SysIntegrationConnection:
        adapter = self._get_adapter(data.provider)
        self._validate_capabilities(adapter.capabilities, data.capabilities)
        self._validate_secret_fields(adapter.required_secret_fields, data.secret_config)
        self.validate_capability_secret_fields(data.provider, data.capabilities, data.secret_config)

        conn = SysIntegrationConnection(
            provider=data.provider,
            name=data.name,
            enabled=data.enabled,
            is_default=data.is_default,
            capabilities=list(data.capabilities),
            config=data.config,
            encrypted_config=self._encrypt_secret_config(data.secret_config),
            sort=data.sort,
            tenant_id=self.tenant_id,
            created_by=self.current_user.id,
            updated_by=self.current_user.id,
        )
        self.db.add(conn)
        await self.db.flush()

        if conn.is_default:
            await self._unset_other_defaults(conn)
        return conn

    async def update_connection(self, connection_id: int, data: IntegrationConnectionUpdate) -> SysIntegrationConnection:
        conn = await self.get_connection(connection_id)
        adapter = self._get_adapter(conn.provider)
        update_data = data.model_dump(exclude_unset=True)
        secret_config = self._decrypt_secret_config(conn.encrypted_config)

        if "capabilities" in update_data and update_data["capabilities"] is not None:
            self._validate_capabilities(adapter.capabilities, update_data["capabilities"])
            conn.capabilities = list(update_data["capabilities"])
        if "secret_config" in update_data and update_data["secret_config"] is not None:
            secret_config.update(update_data["secret_config"])
            conn.encrypted_config = self._encrypt_secret_config(secret_config)
        self._validate_secret_fields(adapter.required_secret_fields, secret_config)
        self.validate_capability_secret_fields(conn.provider, conn.capabilities or [], secret_config)

        for field in ("name", "enabled", "is_default", "config", "sort"):
            if field in update_data and update_data[field] is not None:
                setattr(conn, field, update_data[field])

        conn.updated_by = self.current_user.id
        await self.db.flush()
        if conn.is_default:
            await self._unset_other_defaults(conn)
        return conn

    async def delete_connection(self, connection_id: int) -> None:
        conn = await self.get_connection(connection_id)
        conn.is_deleted = True
        conn.enabled = False
        conn.is_default = False
        conn.updated_by = self.current_user.id

    async def get_connection(self, connection_id: int) -> SysIntegrationConnection:
        conditions = [
            SysIntegrationConnection.id == connection_id,
            SysIntegrationConnection.is_deleted == False,  # noqa: E712
        ]
        if self.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == self.tenant_id)
        conn = await self.db.scalar(select(SysIntegrationConnection).where(*conditions))
        if not conn:
            raise NotFoundException("集成连接")
        return conn

    async def test_connection(self, connection_id: int) -> IntegrationTestResult:
        conn = await self.get_connection(connection_id)
        adapter = self._get_adapter(conn.provider)
        result = await adapter.test(self._build_context(conn))

        conn.last_test_status = "success" if result.success else "failed"
        conn.last_test_message = result.message
        conn.updated_by = self.current_user.id
        await self.db.flush()
        return IntegrationTestResult(
            success=result.success,
            provider=conn.provider,
            message=result.message,
            details=result.details,
        )

    async def send_message(self, data: IntegrationSendMessageRequest) -> IntegrationSendMessageResult:
        conn = await self._resolve_connection(data.connection_id, data.provider)
        adapter = self._get_adapter(conn.provider)
        if "bot_message" not in (conn.capabilities or []):
            raise ValidationException("当前连接未启用机器人消息能力")

        result = await adapter.send_message(
            self._build_context(conn),
            message_type=data.message_type,
            title=data.title,
            content=data.content,
            target=data.target,
            metadata=data.metadata,
        )
        return IntegrationSendMessageResult(
            success=result.success,
            provider=conn.provider,
            connection_id=conn.id,
            message=result.message,
            external_message_id=result.external_message_id,
            raw=result.details,
        )

    def to_output(self, conn: SysIntegrationConnection) -> IntegrationConnectionOut:
        adapter = self._get_adapter(conn.provider)
        return IntegrationConnectionOut(
            id=conn.id,
            provider=conn.provider,
            provider_name=adapter.name,
            name=conn.name,
            enabled=conn.enabled,
            is_default=conn.is_default,
            capabilities=conn.capabilities or [],
            config=conn.config or {},
            secret_configured=bool(conn.encrypted_config),
            status=conn.status,
            last_test_status=conn.last_test_status,
            last_test_message=conn.last_test_message,
            sort=conn.sort,
            tenant_id=conn.tenant_id,
        )

    async def _resolve_connection(self, connection_id: int | None, provider: str | None) -> SysIntegrationConnection:
        if connection_id:
            conn = await self.get_connection(connection_id)
            if not conn.enabled or conn.status != 1:
                raise ValidationException("集成连接未启用")
            return conn

        conditions = [
            SysIntegrationConnection.is_deleted == False,  # noqa: E712
            SysIntegrationConnection.enabled == True,  # noqa: E712
            SysIntegrationConnection.status == 1,
            SysIntegrationConnection.is_default == True,  # noqa: E712
        ]
        if self.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == self.tenant_id)
        if provider:
            conditions.append(SysIntegrationConnection.provider == provider)

        conn = await self.db.scalar(
            select(SysIntegrationConnection)
            .where(*conditions)
            .order_by(SysIntegrationConnection.sort, SysIntegrationConnection.created_at)
            .limit(1)
        )
        if not conn:
            raise NotFoundException("默认集成连接")
        return conn

    async def _unset_other_defaults(self, conn: SysIntegrationConnection) -> None:
        conditions = [
            SysIntegrationConnection.id != conn.id,
            SysIntegrationConnection.provider == conn.provider,
            SysIntegrationConnection.is_deleted == False,  # noqa: E712
        ]
        if conn.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == conn.tenant_id)
        await self.db.execute(
            update(SysIntegrationConnection)
            .where(and_(*conditions))
            .values(is_default=False)
        )

    def _build_context(self, conn: SysIntegrationConnection) -> AdapterContext:
        return AdapterContext(
            provider=conn.provider,
            config=conn.config or {},
            secret_config=self._decrypt_secret_config(conn.encrypted_config),
        )

    @staticmethod
    def _get_adapter(provider: str):
        try:
            return integration_registry.get(provider)
        except KeyError as exc:
            raise ValidationException(f"不支持的集成平台: {provider}") from exc

    @staticmethod
    def _validate_capabilities(supported: Sequence[str], selected: Sequence[str]) -> None:
        unsupported = [item for item in selected if item not in supported]
        if unsupported:
            raise ValidationException(f"平台不支持能力: {', '.join(unsupported)}")

    @staticmethod
    def _validate_secret_fields(required_fields: list[str], secret_config: dict[str, str]) -> None:
        missing = [field for field in required_fields if not secret_config.get(field)]
        if missing:
            raise ValidationException(f"缺少敏感配置: {', '.join(missing)}")

    @staticmethod
    def validate_capability_secret_fields(provider: str, capabilities: Sequence[str], secret_config: dict[str, str]) -> None:
        required_map: dict[str, dict[str, list[str]]] = {
            "feishu": {
                "oauth": ["app_id", "app_secret"],
                "contact_sync": ["app_id", "app_secret"],
            },
            "dingtalk": {
                "oauth": ["app_key", "app_secret"],
                "contact_sync": ["app_key", "app_secret"],
            },
            "wecom": {
                "contact_sync": ["corp_id", "corp_secret"],
            },
        }
        required_fields: list[str] = []
        for capability in capabilities:
            required_fields.extend(required_map.get(provider, {}).get(capability, []))
        missing = [field for field in dict.fromkeys(required_fields) if not secret_config.get(field)]
        if missing:
            raise ValidationException(f"当前启用能力缺少敏感配置: {', '.join(missing)}")

    @staticmethod
    def _encrypt_secret_config(secret_config: dict[str, str]) -> str | None:
        clean = {k: v for k, v in secret_config.items() if v}
        if not clean:
            return None
        return encrypt_value(json.dumps(clean, ensure_ascii=False))

    @staticmethod
    def _decrypt_secret_config(encrypted_config: str | None) -> dict[str, str]:
        if not encrypted_config:
            return {}
        try:
            data = json.loads(decrypt_value(encrypted_config))
        except Exception as exc:
            raise ValidationException("敏感配置解密失败，请重新保存连接配置") from exc
        return data if isinstance(data, dict) else {}
