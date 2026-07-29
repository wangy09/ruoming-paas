"""
若茗 PaaS - 系统 Repository
提供部门、字典数据访问方法
Author: ruoming
"""
from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.system.models import SysDictType, SysDictItem, SysDept


class DictTypeRepository(TenantAwareRepository):
    """字典类型数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_types(
        self,
        *,
        keyword: str | None = None,
        status: int | None = None,
    ) -> list[SysDictType]:
        """获取字典类型列表"""
        query = await self._base_query(SysDictType)
        if keyword:
            query = query.where(
                or_(
                    SysDictType.name.ilike(f"%{keyword}%"),
                    SysDictType.code.ilike(f"%{keyword}%"),
                )
            )
        if status is not None:
            query = query.where(SysDictType.status == status)
        query = query.order_by(SysDictType.sort)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> SysDictType | None:
        """根据编码获取字典类型"""
        query = select(SysDictType).where(
            SysDictType.code == code,
            SysDictType.is_deleted == False,
            SysDictType.status == 1,
        )
        if self.tenant_id is not None:
            query = query.where(SysDictType.tenant_id == self.tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_items(self, type_id: int) -> tuple[SysDictType | None, list[SysDictItem]]:
        """获取字典类型及其所有字典项"""
        dict_type = await self.get_by_id(SysDictType, type_id)
        if not dict_type:
            return None, []

        items_query = select(SysDictItem).where(
            SysDictItem.type_id == type_id,
            SysDictItem.is_deleted == False,
        ).order_by(SysDictItem.sort)
        items_result = await self.db.execute(items_query)
        return dict_type, list(items_result.scalars().all())

    async def soft_delete_type(self, type_id: int) -> None:
        """软删除字典类型及其所有字典项"""
        dict_type = await self.get_by_id(SysDictType, type_id)
        if dict_type:
            dict_type.is_deleted = True
            await self.db.execute(
                update(SysDictItem)
                .where(SysDictItem.type_id == type_id)
                .values(is_deleted=True)
            )
            await self.db.flush()


class DictItemRepository(TenantAwareRepository):
    """字典项数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_items(self, type_id: int) -> list[SysDictItem]:
        """获取字典项列表"""
        query = select(SysDictItem).where(
            SysDictItem.type_id == type_id,
            SysDictItem.is_deleted == False,
        ).order_by(SysDictItem.sort)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_type_and_value(self, type_id: int, value: str) -> SysDictItem | None:
        """根据类型和值获取字典项"""
        query = select(SysDictItem).where(
            SysDictItem.type_id == type_id,
            SysDictItem.value == value,
            SysDictItem.is_deleted == False,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


class DeptRepository(TenantAwareRepository):
    """部门数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_depts(
        self,
        *,
        parent_id: int | None = None,
        status: int | None = None,
    ) -> list[SysDept]:
        """获取部门列表"""
        query = await self._base_query(SysDept)
        if parent_id is not None:
            query = query.where(SysDept.parent_id == parent_id)
        if status is not None:
            query = query.where(SysDept.status == status)
        query = query.order_by(SysDept.level, SysDept.sort)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_dept_by_id(self, dept_id: int) -> SysDept | None:
        """根据 ID 获取部门"""
        return await self.get_by_id(SysDept, dept_id)
