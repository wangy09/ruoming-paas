from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.customer_order3.models import CustomerOrder3


class CustomerOrder3Repository(TenantAwareRepository):
    """客户订单数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_by_id(self, obj_id: int) -> CustomerOrder3 | None:
        return await super().get_by_id(CustomerOrder3, obj_id)

    async def list_all(self) -> list[CustomerOrder3]:
        return await super().list_all(CustomerOrder3)