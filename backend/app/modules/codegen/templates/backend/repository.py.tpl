from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.{{ module_name }}.models import {{ entity_name }}


class {{ entity_name }}Repository(TenantAwareRepository):
    """{{ page_title }}数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_by_id(self, obj_id: int) -> {{ entity_name }} | None:
        return await super().get_by_id({{ entity_name }}, obj_id)

    async def list_all(self) -> list[{{ entity_name }}]:
        return await super().list_all({{ entity_name }})