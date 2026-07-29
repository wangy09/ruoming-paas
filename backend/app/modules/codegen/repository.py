"""
若茗 PaaS - 代码生成器 Repository
提供代码生成配置的数据访问方法
Author: ruoming
"""
from sqlalchemy import select, func, delete, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.codegen.models import GenTable, GenTableColumn


class CodegenRepository(TenantAwareRepository):
    """代码生成器数据访问层"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(db, tenant_id)

    async def list_configs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[GenTable], int]:
        """查询代码生成配置列表"""
        query = await self._base_query(GenTable)
        if keyword:
            query = query.where(
                GenTable.table_name.ilike(f"%{keyword}%")
                | GenTable.table_comment.ilike(f"%{keyword}%")
                | GenTable.module_name.ilike(f"%{keyword}%")
            )
        query = query.order_by(GenTable.created_at.desc())
        return await self.paginate(query, page=page, page_size=page_size)

    async def get_by_id(self, config_id: int) -> GenTable | None:
        """根据 ID 获取配置"""
        return await super().get_by_id(GenTable, config_id)

    async def get_config_with_columns(self, config_id: int) -> tuple[GenTable | None, list[GenTableColumn]]:
        """获取配置及其所有列"""
        table = await self.get_by_id(config_id)
        if not table:
            return None, []

        columns_query = select(GenTableColumn).where(
            GenTableColumn.table_id == config_id,
            GenTableColumn.is_deleted == False,
        ).order_by(GenTableColumn.sort)
        columns = await self.db.execute(columns_query)
        return table, columns.scalars().all()

    async def batch_get_columns(self, table_ids: list[int]) -> dict[int, list[GenTableColumn]]:
        """批量获取多个表的列信息"""
        if not table_ids:
            return {}

        columns_query = select(GenTableColumn).where(
            GenTableColumn.table_id.in_(table_ids),
            GenTableColumn.is_deleted == False,
        ).order_by(GenTableColumn.table_id, GenTableColumn.sort)
        all_columns = await self.db.execute(columns_query)

        result: dict[int, list[GenTableColumn]] = {}
        for col in all_columns.scalars().all():
            result.setdefault(col.table_id, []).append(col)
        return result

    async def check_table_exists(self, table_name: str) -> bool:
        """检查表是否存在于数据库中"""
        check_sql = text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"
        )
        result = await self.db.execute(check_sql, {"name": table_name.lower()})
        return bool(result.scalar_one())

    async def batch_check_tables_exist(self, table_names: list[str]) -> set[str]:
        """批量检查表是否存在"""
        if not table_names:
            return set()

        placeholders = ", ".join([f":t{i}" for i in range(len(table_names))])
        exists_sql = text(
            f"SELECT table_name FROM information_schema.tables WHERE table_name IN ({placeholders})"
        )
        params = {f"t{i}": name.lower() for i, name in enumerate(table_names)}
        result = await self.db.execute(exists_sql, params)
        return {row[0] for row in result.all()}

    async def get_by_table_name(self, table_name: str) -> GenTable | None:
        """根据表名获取配置"""
        query = select(GenTable).where(
            GenTable.table_name == table_name,
            GenTable.is_deleted == False,
        )
        if self.tenant_id is not None:
            query = query.where(GenTable.tenant_id == self.tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def soft_delete(self, obj: GenTable) -> None:
        """软删除配置及其列"""
        obj.is_deleted = True
        await self.db.execute(
            update(GenTableColumn)
            .where(GenTableColumn.table_id == obj.id)
            .values(is_deleted=True)
        )
        await self.db.flush()

    async def save_columns(self, table_id: int, columns: list[GenTableColumn]) -> None:
        """保存列配置（先删除旧列再插入新列）"""
        await self.db.execute(
            delete(GenTableColumn).where(GenTableColumn.table_id == table_id)
        )
        for col in columns:
            self.db.add(col)
        await self.db.flush()
