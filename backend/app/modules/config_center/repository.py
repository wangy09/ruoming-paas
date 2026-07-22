from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.config_center.models import SysConfig


class ConfigRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_by_id(self, obj_id: int) -> SysConfig | None:
        return await super().get_by_id(SysConfig, obj_id)

    async def get_by_key_and_scope(
        self,
        config_key: str,
        scope: str,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
    ) -> SysConfig | None:
        query = await self._base_query(SysConfig)
        query = query.where(SysConfig.config_key == config_key)
        query = query.where(SysConfig.scope == scope)
        if tenant_id is not None:
            query = query.where(SysConfig.tenant_id == tenant_id)
        if app_key is not None:
            query = query.where(SysConfig.app_key == app_key)
        if user_id is not None:
            query = query.where(SysConfig.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_scope(
        self,
        scope: str,
        *,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
        category: str | None = None,
        keyword: str | None = None,
        is_public: bool | None = None,
        is_encrypted: bool | None = None,
        status: int | None = None,
    ) -> list[SysConfig]:
        query = await self._base_query(SysConfig)
        query = query.where(SysConfig.scope == scope)
        if tenant_id is not None:
            query = query.where(SysConfig.tenant_id == tenant_id)
        else:
            query = query.where(SysConfig.tenant_id == None)
        if app_key is not None:
            query = query.where(SysConfig.app_key == app_key)
        if user_id is not None:
            query = query.where(SysConfig.user_id == user_id)
        if category:
            query = query.where(SysConfig.category == category)
        if keyword:
            like = f"%{keyword}%"
            query = query.where(
                SysConfig.config_key.ilike(like)
                | SysConfig.label.ilike(like)
                | SysConfig.description.ilike(like)
            )
        if is_public is not None:
            query = query.where(SysConfig.is_public == is_public)
        if is_encrypted is not None:
            query = query.where(SysConfig.is_encrypted == is_encrypted)
        if status is not None:
            query = query.where(SysConfig.status == status)
        query = query.order_by(asc(SysConfig.sort), asc(SysConfig.id))
        result = await self.db.execute(query)
        return list(result.scalars().all())
