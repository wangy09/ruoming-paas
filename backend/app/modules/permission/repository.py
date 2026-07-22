from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.permission.models import SysRole, SysUserRole


class RoleRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_role_by_id(self, obj_id: int) -> SysRole | None:
        return await super().get_by_id(SysRole, obj_id)

    async def get_by_code(self, code: str) -> SysRole | None:
        query = await self._base_query(SysRole)
        query = query.where(SysRole.code == code)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_roles(self) -> list[SysRole]:
        return await super().list_all(SysRole)


class UserRoleRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_user_roles(self, user_id: int) -> list[tuple[int, str, str]]:
        query = select(SysRole.id, SysRole.name, SysRole.code).join(
            SysUserRole, SysRole.id == SysUserRole.role_id
        ).where(SysUserRole.user_id == user_id).where(SysRole.is_deleted == False)
        result = await self.db.execute(query)
        rows = result.all()
        return [(int(row[0]), str(row[1]), str(row[2])) for row in rows]

    async def delete_by_user_id(self, user_id: int) -> None:
        from sqlalchemy import delete
        await self.db.execute(delete(SysUserRole).where(SysUserRole.user_id == user_id))
