from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.file_center.models import SysFile


class FileRepository(TenantAwareRepository):
    def __init__(self, db: AsyncSession, tenant_id: int | None):
        super().__init__(db, tenant_id)

    async def get_file_by_id(self, obj_id: int) -> SysFile | None:
        return await super().get_by_id(SysFile, obj_id)

    async def get_by_hash(self, file_hash: str) -> SysFile | None:
        query = await self._base_query(SysFile)
        query = query.where(SysFile.file_hash == file_hash)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_files(self) -> list[SysFile]:
        return await super().list_all(SysFile)
