"""
若茗 PaaS - 多租户感知 Repository 基类
所有业务 Repository 必须继承此类，自动注入 tenant_id 过滤条件
Author: ruoming
"""
import math
from typing import Any, TypeVar

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.base_model import BaseModel

logger = structlog.get_logger("security")

ModelT = TypeVar("ModelT", bound=BaseModel)


class TenantAwareRepository:
    """
    多租户感知 Repository 基类。

    约束：
    - 所有数据访问自动注入 tenant_id 过滤，防止跨租户访问
    - get_by_id 额外做兜底检查，即使子类漏写过滤也能拦截
    - 如需访问全租户数据（平台超管），传入 tenant_id=None

    用法::

        class UserRepository(TenantAwareRepository):
            async def get_active_users(self) -> list[SysUser]:
                query = self._base_query(SysUser)
                query = query.where(SysUser.status == 1)
                result = await self.db.execute(query)
                return list(result.scalars().all())
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # ── 查询基础方法 ──────────────────────────────────────────────────

    async def _base_query(self, model: type[ModelT]):
        """构建带 tenant_id 过滤 + 软删除过滤的基础查询"""
        query = select(model).where(model.is_deleted == False)  # noqa: E712

        from app.core.multi_tenant import is_multi_tenant_enabled

        if self.tenant_id is not None and await is_multi_tenant_enabled():
            if not hasattr(model, "tenant_id"):
                logger.warning(
                    "model_missing_tenant_id",
                    model=model.__name__,
                    tenant_id=self.tenant_id,
                )
            else:
                query = query.where(model.tenant_id == self.tenant_id)
        return query

    async def get_by_id(self, model: type[ModelT], record_id: int) -> ModelT | None:
        """按 ID 查询单条记录，带兜底跨租户检查"""
        query = await self._base_query(model)
        query = query.where(model.id == record_id)
        result = await self.db.execute(query)
        obj = result.scalar_one_or_none()

        # 兜底防护：即使子类忘记 tenant_id 过滤，也在此拦截
        if obj is not None and self.tenant_id is not None:
            if hasattr(obj, "tenant_id") and obj.tenant_id != self.tenant_id:
                logger.error(
                    "cross_tenant_access_blocked",
                    model=model.__name__,
                    record_id=record_id,
                    record_tenant_id=obj.tenant_id,
                    request_tenant_id=self.tenant_id,
                )
                return None

        return obj

    async def list_all(self, model: type[ModelT]) -> list[ModelT]:
        """查询全部（无分页）"""
        result = await self.db.execute(await self._base_query(model))
        return list(result.scalars().all())

    async def paginate(
        self,
        query,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        """
        分页查询通用方法。
        返回 (items, total)
        """
        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # 数据
        offset = (page - 1) * page_size
        data_query = query.offset(offset).limit(page_size)
        data_result = await self.db.execute(data_query)
        items = list(data_result.scalars().all())

        return items, total

    # ── 写操作 ────────────────────────────────────────────────────────

    async def create(self, obj: ModelT) -> ModelT:
        """持久化新对象"""
        if self.tenant_id is not None and hasattr(obj, "tenant_id"):
            if obj.tenant_id is None:
                obj.tenant_id = self.tenant_id
        self.db.add(obj)
        await self.db.flush()   # 获取自增 ID，但不提交事务
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelT, **kwargs: Any) -> ModelT:
        """更新对象字段"""
        for k, v in kwargs.items():
            setattr(obj, k, v)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: ModelT) -> None:
        """软删除"""
        obj.is_deleted = True  # type: ignore[attr-defined]
        await self.db.flush()

    async def hard_delete(self, obj: ModelT) -> None:
        """物理删除（谨慎使用）"""
        await self.db.delete(obj)
        await self.db.flush()

    async def count(self, model: type[ModelT]) -> int:
        """统计当前租户下的记录数"""
        base_query = await self._base_query(model)
        query = select(func.count()).select_from(base_query.subquery())
        result = await self.db.execute(query)
        return result.scalar_one()
