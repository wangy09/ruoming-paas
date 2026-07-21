from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.utils.pagination import PageParams
from app.modules.audit.service import audit_log
from app.modules.{{ module_name }}.models import {{ entity_name }}
from app.modules.{{ module_name }}.repository import {{ entity_name }}Repository
from app.modules.{{ module_name }}.schemas import {{ entity_name }}Create, {{ entity_name }}Update


class {{ entity_name }}Service:
    """{{ page_title }}服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        self.db = db
        self.repo = {{ entity_name }}Repository(db, tenant_id)

    async def list(self, page_params: PageParams, keyword: str | None = None) -> dict:
        query = await self.repo._base_query({{ entity_name }})

{% if has_search_fields %}        if keyword:
            query = query.where(
                {% for field in searchable_fields %}
                {{ entity_name }}.{{ field }}.ilike(f"%{keyword}%"){% if not loop.last %} | {% endif %}
                {% endfor %}
            )
{% endif %}

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.db.execute(
            query.order_by(desc({{ entity_name }}.created_at))
            .offset(page_params.offset)
            .limit(page_params.page_size)
        )
        return {
            "items": rows.scalars().all(),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def get(self, obj_id: int) -> {{ entity_name }}:
        obj = await self.repo.get_by_id(obj_id)
        if not obj:
            raise NotFoundException("{{ page_title }}")
        return obj

    @audit_log("{{ module_name }}.create", module="{{ module_name }}", action="create", resource_type="{{ table_name }}")
    async def create(self, data: {{ entity_name }}Create) -> {{ entity_name }}:
        obj = {{ entity_name }}(**data.model_dump(exclude_unset=True))
        await self.repo.create(obj)
        return obj

    @audit_log("{{ module_name }}.update", module="{{ module_name }}", action="update", resource_type="{{ table_name }}")
    async def update(self, obj_id: int, data: {{ entity_name }}Update) -> {{ entity_name }}:
        obj = await self.get(obj_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    @audit_log("{{ module_name }}.delete", module="{{ module_name }}", action="delete", resource_type="{{ table_name }}")
    async def delete(self, obj_id: int) -> None:
        obj = await self.get(obj_id)
        await self.repo.soft_delete(obj)