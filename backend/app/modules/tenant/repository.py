from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.tenant.models import SysTenant


class TenantRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_tenant_by_id(self, obj_id: int) -> SysTenant | None:
        return await super().get_by_id(SysTenant, obj_id)

    async def get_by_code(self, code: str) -> SysTenant | None:
        query = await self._base_query(SysTenant)
        query = query.where(SysTenant.code == code)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_tenants(self) -> list[SysTenant]:
        return await super().list_all(SysTenant)
