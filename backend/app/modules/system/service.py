"""
若茗 PaaS - 字典服务
"""
from typing import Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import SysDictType, SysDictItem
from app.modules.system.schemas import DictTypeCreate, DictTypeUpdate, DictItemCreate, DictItemUpdate


class DictService:
    """字典服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dict_types(
        self,
        tenant_id: int | None = None,
        keyword: str | None = None,
        status: int | None = None,
    ) -> Sequence[SysDictType]:
        """获取字典类型列表"""
        from sqlalchemy import or_

        query = select(SysDictType).where(SysDictType.is_deleted == False)
        if tenant_id:
            query = query.where(SysDictType.tenant_id == tenant_id)
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
        return result.scalars().all()

    async def get_dict_type(self, type_id: int) -> SysDictType | None:
        """获取字典类型详情"""
        query = select(SysDictType).where(
            SysDictType.id == type_id,
            SysDictType.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_dict_type_with_items(self, type_id: int) -> tuple[SysDictType, list[SysDictItem]]:
        """获取字典类型（含字典项）"""
        type_query = select(SysDictType).where(
            SysDictType.id == type_id,
            SysDictType.is_deleted == False
        )
        type_result = await self.db.execute(type_query)
        dict_type = type_result.scalar_one_or_none()
        if not dict_type:
            return None, []

        items_query = select(SysDictItem).where(
            SysDictItem.type_id == type_id,
            SysDictItem.is_deleted == False
        ).order_by(SysDictItem.sort)
        items_result = await self.db.execute(items_query)
        return dict_type, items_result.scalars().all()

    async def create_dict_type(self, data: DictTypeCreate, tenant_id: int | None = None) -> SysDictType:
        """创建字典类型"""
        dict_type = SysDictType(
            name=data.name,
            code=data.code,
            description=data.description,
            sort=data.sort,
            status=data.status,
            tenant_id=tenant_id,
        )
        self.db.add(dict_type)
        await self.db.commit()
        await self.db.refresh(dict_type)
        return dict_type

    async def update_dict_type(self, type_id: int, data: DictTypeUpdate) -> SysDictType | None:
        """更新字典类型"""
        dict_type = await self.get_dict_type(type_id)
        if not dict_type:
            return None

        if data.name is not None:
            dict_type.name = data.name
        if data.code is not None:
            dict_type.code = data.code
        if data.description is not None:
            dict_type.description = data.description
        if data.sort is not None:
            dict_type.sort = data.sort
        if data.status is not None:
            dict_type.status = data.status

        await self.db.commit()
        await self.db.refresh(dict_type)
        return dict_type

    async def delete_dict_type(self, type_id: int) -> bool:
        """删除字典类型"""
        dict_type = await self.get_dict_type(type_id)
        if not dict_type:
            return False
        if dict_type.is_system:
            return False

        dict_type.is_deleted = True
        await self.db.execute(
            update(SysDictItem)
            .where(SysDictItem.type_id == type_id)
            .values(is_deleted=True)
        )
        await self.db.commit()
        return True

    async def get_dict_items(self, type_id: int) -> Sequence[SysDictItem]:
        """获取字典项列表"""
        query = select(SysDictItem).where(
            SysDictItem.type_id == type_id,
            SysDictItem.is_deleted == False
        ).order_by(SysDictItem.sort)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_dict_item(self, item_id: int) -> SysDictItem | None:
        """获取字典项详情"""
        query = select(SysDictItem).where(
            SysDictItem.id == item_id,
            SysDictItem.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_dict_item(self, data: DictItemCreate) -> SysDictItem:
        """创建字典项"""
        dict_item = SysDictItem(
            type_id=data.type_id,
            label=data.label,
            value=data.value,
            description=data.description,
            sort=data.sort,
            status=data.status,
            is_default=data.is_default,
            css_class=data.css_class,
        )
        self.db.add(dict_item)
        await self.db.commit()
        await self.db.refresh(dict_item)
        return dict_item

    async def update_dict_item(self, item_id: int, data: DictItemUpdate) -> SysDictItem | None:
        """更新字典项"""
        dict_item = await self.get_dict_item(item_id)
        if not dict_item:
            return None

        if data.label is not None:
            dict_item.label = data.label
        if data.value is not None:
            dict_item.value = data.value
        if data.description is not None:
            dict_item.description = data.description
        if data.sort is not None:
            dict_item.sort = data.sort
        if data.status is not None:
            dict_item.status = data.status
        if data.is_default is not None:
            dict_item.is_default = data.is_default
        if data.css_class is not None:
            dict_item.css_class = data.css_class

        await self.db.commit()
        await self.db.refresh(dict_item)
        return dict_item

    async def delete_dict_item(self, item_id: int) -> bool:
        """删除字典项"""
        dict_item = await self.get_dict_item(item_id)
        if not dict_item:
            return False

        dict_item.is_deleted = True
        await self.db.commit()
        return True

    async def get_dict_by_code(self, code: str, tenant_id: int | None = None) -> tuple[SysDictType, list[SysDictItem]]:
        """根据编码获取字典类型和字典项"""
        query = select(SysDictType).where(
            SysDictType.code == code,
            SysDictType.is_deleted == False,
            SysDictType.status == 1,
        )
        if tenant_id:
            query = query.where(SysDictType.tenant_id == tenant_id)
        result = await self.db.execute(query)
        dict_type = result.scalar_one_or_none()
        if not dict_type:
            return None, []

        items_query = select(SysDictItem).where(
            SysDictItem.type_id == dict_type.id,
            SysDictItem.is_deleted == False,
            SysDictItem.status == 1,
        ).order_by(SysDictItem.sort)
        items_result = await self.db.execute(items_query)
        return dict_type, items_result.scalars().all()
