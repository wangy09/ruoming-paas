"""
若茗 PaaS - Prompt 模板服务层
Author: ruoming
"""
from __future__ import annotations

import json
import re

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompt.models import AiPromptTemplate, AiPromptVersion
from app.ai.prompt.schemas import PromptTemplateCreate, PromptVersionCreate
from app.core.exceptions import NotFoundException
from app.core.utils.pagination import PageParams

logger = structlog.get_logger(__name__)

# Redis 缓存 TTL（秒）
_PROMPT_CACHE_TTL = 300


class PromptService:
    def __init__(self, db: AsyncSession, redis=None) -> None:
        self.db = db
        self.redis = redis

    # ── 模板 CRUD ──────────────────────────────────────────────────────────────

    async def get_list(
        self,
        tenant_id: int | None,
        params: PageParams,
        category: str | None = None,
    ) -> tuple[list[AiPromptTemplate], int]:
        stmt = select(AiPromptTemplate).where(AiPromptTemplate.is_deleted == False)
        if tenant_id is not None:
            stmt = stmt.where(AiPromptTemplate.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(AiPromptTemplate.category == category)

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiPromptTemplate.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def create(
        self, data: PromptTemplateCreate, tenant_id: int | None, user_id: int
    ) -> AiPromptTemplate:
        template = AiPromptTemplate(
            name=data.name,
            description=data.description,
            category=data.category,
            variables=data.variables,
            current_version=1,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        self.db.add(template)
        await self.db.flush()

        # 建立 v1 版本（初始草稿，未发布）
        version = AiPromptVersion(
            template_id=template.id,
            version=1,
            content=data.content,
            changelog=data.changelog or "初始版本",
            is_published=False,
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete(self, template_id: int) -> None:
        tmpl = await self.db.get(AiPromptTemplate, template_id)
        if not tmpl or tmpl.is_deleted:
            raise NotFoundException(f"Prompt 模板 ID={template_id} 不存在")
        tmpl.is_deleted = True
        await self.db.commit()

    # ── 版本管理 ───────────────────────────────────────────────────────────────

    async def get_versions(self, template_id: int) -> list[AiPromptVersion]:
        result = await self.db.execute(
            select(AiPromptVersion)
            .where(AiPromptVersion.template_id == template_id)
            .order_by(AiPromptVersion.version.desc())
        )
        return list(result.scalars().all())

    async def add_version(
        self, template_id: int, data: PromptVersionCreate, user_id: int
    ) -> AiPromptVersion:
        """提交新版本（原版本保留不修改）"""
        tmpl = await self.db.get(AiPromptTemplate, template_id)
        if not tmpl or tmpl.is_deleted:
            raise NotFoundException(f"Prompt 模板 ID={template_id} 不存在")

        new_version_num = tmpl.current_version + 1
        version = AiPromptVersion(
            template_id=template_id,
            version=new_version_num,
            content=data.content,
            changelog=data.changelog or f"版本 {new_version_num}",
            is_published=False,
            created_by=user_id,
        )
        self.db.add(version)
        tmpl.current_version = new_version_num
        await self.db.commit()
        await self.db.refresh(version)

        # 清除该模板的 Redis 缓存
        await self._invalidate_cache(template_id)
        return version

    async def publish_version(self, template_id: int, version_num: int) -> AiPromptVersion:
        """发布指定版本（发布后可被 Agent 引用）"""
        result = await self.db.execute(
            select(AiPromptVersion)
            .where(AiPromptVersion.template_id == template_id)
            .where(AiPromptVersion.version == version_num)
        )
        version = result.scalar_one_or_none()
        if not version:
            raise NotFoundException(f"版本 {version_num} 不存在")

        version.is_published = True
        await self.db.commit()
        await self._invalidate_cache(template_id)
        return version

    async def rollback(self, template_id: int, version_num: int) -> AiPromptTemplate:
        """回滚到指定版本（修改 current_version，不删数据）"""
        tmpl = await self.db.get(AiPromptTemplate, template_id)
        if not tmpl or tmpl.is_deleted:
            raise NotFoundException(f"Prompt 模板 ID={template_id} 不存在")

        result = await self.db.execute(
            select(AiPromptVersion)
            .where(AiPromptVersion.template_id == template_id)
            .where(AiPromptVersion.version == version_num)
        )
        if not result.scalar_one_or_none():
            raise NotFoundException(f"版本 {version_num} 不存在，无法回滚")

        tmpl.current_version = version_num
        await self.db.commit()
        await self._invalidate_cache(template_id)
        await self.db.refresh(tmpl)
        return tmpl

    # ── Prompt 渲染 ────────────────────────────────────────────────────────────

    async def render(
        self,
        template_id: int,
        variables: dict,
        version: int | None = None,
    ) -> str:
        """
        加载指定版本的 Prompt 模板并插值变量。
        version=None 时使用最新已发布版本。
        """
        version_row = await self._get_version(template_id, version)
        if not version_row:
            raise NotFoundException("未找到可用的 Prompt 版本（请先发布一个版本）")
        return self._interpolate(version_row.content, variables)

    async def _get_version(
        self, template_id: int, version: int | None
    ) -> AiPromptVersion | None:
        """优先从 Redis 缓存加载，Miss 时查 DB"""
        cache_key = f"prompt:{template_id}:{version or 'latest'}"

        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                try:
                    data = json.loads(cached)
                    # 构造一个轻量级对象返回
                    return type("PromptVersionCache", (), data)()
                except Exception:
                    pass

        if version is None:
            result = await self.db.execute(
                select(AiPromptVersion)
                .where(AiPromptVersion.template_id == template_id)
                .where(AiPromptVersion.is_published == True)
                .order_by(AiPromptVersion.version.desc())
                .limit(1)
            )
        else:
            result = await self.db.execute(
                select(AiPromptVersion)
                .where(AiPromptVersion.template_id == template_id)
                .where(AiPromptVersion.version == version)
            )

        row = result.scalar_one_or_none()
        if row and self.redis:
            await self.redis.setex(
                cache_key,
                _PROMPT_CACHE_TTL,
                json.dumps({"content": row.content, "version": row.version}),
            )
        return row

    async def _invalidate_cache(self, template_id: int) -> None:
        if not self.redis:
            return
        try:
            # 删除 latest 和常用版本缓存键（精确匹配）
            keys = await self.redis.keys(f"prompt:{template_id}:*")
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.warning("prompt_cache_invalidate_failed", error=str(e))

    @staticmethod
    def _interpolate(content: str, variables: dict) -> str:
        """将 {{variable}} 插值替换为实际值，未找到的变量保留原占位符"""
        def replace(m: re.Match) -> str:
            key = m.group(1).strip()
            if key in variables:
                return str(variables[key])
            return m.group(0)  # 保留原占位符

        return re.sub(r"\{\{(.+?)\}\}", replace, content)
