from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.message.models import SysNotice, SysMessage


class NoticeRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_by_id(self, obj_id: int) -> SysNotice | None:
        return await super().get_by_id(SysNotice, obj_id)

    async def list_all(self) -> list[SysNotice]:
        return await super().list_all(SysNotice)


class MessageRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_by_id(self, obj_id: int) -> SysMessage | None:
        return await super().get_by_id(SysMessage, obj_id)

    async def list_by_user_id(self, user_id: int) -> list[SysMessage]:
        query = await self._base_query(SysMessage)
        query = query.where(SysMessage.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
