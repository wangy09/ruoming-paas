"""
若茗 PaaS - 集成平台 Repository
提供第三方协作平台集成数据访问方法
Author: ruoming
"""
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.integration.models import (
    SysIntegrationConnection,
    SysExternalIdentity,
    SysContactSyncLog,
)


class IntegrationConnectionRepository(TenantAwareRepository):
    """集成连接数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_connections(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> list[SysIntegrationConnection]:
        """获取集成连接列表"""
        conditions = [SysIntegrationConnection.is_deleted == False]
        if self.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == self.tenant_id)
        if provider:
            conditions.append(SysIntegrationConnection.provider == provider)
        if enabled is not None:
            conditions.append(SysIntegrationConnection.enabled == enabled)

        query = (
            select(SysIntegrationConnection)
            .where(*conditions)
            .order_by(SysIntegrationConnection.sort, SysIntegrationConnection.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_connection_by_id(self, connection_id: int) -> SysIntegrationConnection | None:
        """根据 ID 获取集成连接"""
        return await self.get_by_id(SysIntegrationConnection, connection_id)

    async def get_default_connection(
        self,
        *,
        provider: str | None = None,
    ) -> SysIntegrationConnection | None:
        """获取默认启用的集成连接"""
        conditions = [
            SysIntegrationConnection.is_deleted == False,
            SysIntegrationConnection.enabled == True,
            SysIntegrationConnection.status == 1,
            SysIntegrationConnection.is_default == True,
        ]
        if self.tenant_id is None:
            conditions.append(SysIntegrationConnection.tenant_id.is_(None))
        else:
            conditions.append(SysIntegrationConnection.tenant_id == self.tenant_id)
        if provider:
            conditions.append(SysIntegrationConnection.provider == provider)

        query = (
            select(SysIntegrationConnection)
            .where(*conditions)
            .order_by(SysIntegrationConnection.sort, SysIntegrationConnection.created_at)
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def unset_other_defaults(self, conn: SysIntegrationConnection) -> None:
        """取消同平台其他连接的默认状态"""
        conditions = [
            SysIntegrationConnection.id != conn.id,
            SysIntegrationConnection.provider == conn.provider,
            SysIntegrationConnection.is_deleted == False,
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


class ExternalIdentityRepository(TenantAwareRepository):
    """外部身份映射数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_by_connection(
        self,
        connection_id: int,
        identity_type: str | None = None,
    ) -> list[SysExternalIdentity]:
        """根据连接获取外部身份映射"""
        query = select(SysExternalIdentity).where(
            SysExternalIdentity.connection_id == connection_id,
        )
        if identity_type:
            query = query.where(SysExternalIdentity.identity_type == identity_type)
        query = query.order_by(SysExternalIdentity.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def batch_upsert(self, identities: list[SysExternalIdentity]) -> None:
        """批量更新或插入外部身份映射"""
        for identity in identities:
            existing = await self.db.scalar(
                select(SysExternalIdentity).where(
                    SysExternalIdentity.connection_id == identity.connection_id,
                    SysExternalIdentity.identity_type == identity.identity_type,
                    SysExternalIdentity.external_id == identity.external_id,
                )
            )
            if existing:
                existing.local_id = identity.local_id
                existing.raw_data = identity.raw_data
            else:
                self.db.add(identity)
        await self.db.flush()


class ContactSyncLogRepository(TenantAwareRepository):
    """通讯录同步日志数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_logs(
        self,
        *,
        connection_id: int | None = None,
        operation: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SysContactSyncLog], int]:
        """获取同步日志列表"""
        query = select(SysContactSyncLog).where()
        if connection_id:
            query = query.where(SysContactSyncLog.connection_id == connection_id)
        if operation:
            query = query.where(SysContactSyncLog.operation == operation)
        if status:
            query = query.where(SysContactSyncLog.status == status)
        query = query.order_by(SysContactSyncLog.id.desc())
        return await self.paginate(query, page=page, page_size=page_size)
