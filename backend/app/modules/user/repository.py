from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.user.models import SysUser


class UserRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_user_by_id(self, obj_id: int) -> SysUser | None:
        return await super().get_by_id(SysUser, obj_id)

    async def get_by_username(self, username: str) -> SysUser | None:
        query = await self._base_query(SysUser)
        query = query.where(SysUser.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username_or_email(self, username: str) -> SysUser | None:
        query = await self._base_query(SysUser)
        query = query.where(or_(SysUser.username == username, SysUser.email == username))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[SysUser]:
        return await super().list_all(SysUser)
