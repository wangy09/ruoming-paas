from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.utils.pagination import PageParams
from app.modules.audit.service import audit_log
from app.modules.customer_order3.models import CustomerOrder3
from app.modules.customer_order3.repository import CustomerOrder3Repository
from app.modules.customer_order3.schemas import CustomerOrder3Create, CustomerOrder3Update


class CustomerOrder3Service:
    """客户订单服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        self.db = db
        self.repo = CustomerOrder3Repository(db, tenant_id)

    async def list(self, page_params: PageParams, keyword: str | None = None) -> dict:
        query = await self.repo._base_query(CustomerOrder3)

        if keyword:
            query = query.where(
                CustomerOrder3.title.ilike(f"%{keyword}%")            )

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.db.execute(
            query.order_by(desc(CustomerOrder3.created_at))
            .offset(page_params.offset)
            .limit(page_params.page_size)
        )
        return {
            "items": rows.scalars().all(),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def get(self, obj_id: int) -> CustomerOrder3:
        obj = await self.repo.get_by_id(obj_id)
        if not obj:
            raise NotFoundException("客户订单")
        return obj

    @audit_log("customer_order3.create", module="customer_order3", action="create", resource_type="customer_order3")
    async def create(self, data: CustomerOrder3Create) -> CustomerOrder3:
        obj = CustomerOrder3(**data.model_dump(exclude_unset=True))
        await self.repo.create(obj)
        return obj

    @audit_log("customer_order3.update", module="customer_order3", action="update", resource_type="customer_order3")
    async def update(self, obj_id: int, data: CustomerOrder3Update) -> CustomerOrder3:
        obj = await self.get(obj_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @audit_log("customer_order3.delete", module="customer_order3", action="delete", resource_type="customer_order3")
    async def delete(self, obj_id: int) -> None:
        obj = await self.get(obj_id)
        await self.repo.soft_delete(obj)