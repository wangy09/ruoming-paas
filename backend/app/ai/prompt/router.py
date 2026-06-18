"""
若茗 PaaS - Prompt 模板版本管理路由
/api/v1/ai/prompts
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompt.schemas import (
    PromptRenderRequest,
    PromptTemplateCreate,
    PromptTemplateInfo,
    PromptVersionCreate,
    PromptVersionInfo,
)
from app.ai.prompt.service import PromptService
from app.core.deps import get_current_user, require_permissions
from app.core.redis import get_redis
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/prompts", tags=["AI-Prompt模板"])


@router.get("", response_model=ApiResponse[PageData[PromptTemplateInfo]], summary="Prompt 模板列表")
async def list_templates(
    category: str | None = Query(None, description="按分类过滤"),
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: SysUser = Depends(get_current_user),
):
    svc = PromptService(db, redis)
    items, total = await svc.get_list(current_user.tenant_id, page_params, category)
    return paged(items=[PromptTemplateInfo.model_validate(i) for i in items], total=total, params=page_params)


@router.post("", response_model=ApiResponse[PromptTemplateInfo], summary="创建 Prompt 模板", status_code=201)
async def create_template(
    data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: SysUser = Depends(require_permissions("ai:prompt:create")),
):
    svc = PromptService(db, redis)
    tmpl = await svc.create(data, current_user.tenant_id, current_user.id)
    return created(PromptTemplateInfo.model_validate(tmpl))


@router.delete("/{template_id}", response_model=ApiResponse, summary="删除 Prompt 模板")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    _: SysUser = Depends(require_permissions("ai:prompt:delete")),
):
    svc = PromptService(db, redis)
    await svc.delete(template_id)
    return ok(message="删除成功")


# ── 版本管理 ──────────────────────────────────────────────────────────────────

@router.get("/{template_id}/versions", response_model=ApiResponse[list[PromptVersionInfo]], summary="版本历史")
async def get_versions(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = PromptService(db)
    versions = await svc.get_versions(template_id)
    return ok([PromptVersionInfo.model_validate(v) for v in versions])


@router.post("/{template_id}/versions", response_model=ApiResponse[PromptVersionInfo], summary="提交新版本", status_code=201)
async def add_version(
    template_id: int,
    data: PromptVersionCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user: SysUser = Depends(require_permissions("ai:prompt:create")),
):
    svc = PromptService(db, redis)
    version = await svc.add_version(template_id, data, current_user.id)
    return created(PromptVersionInfo.model_validate(version))


@router.post("/{template_id}/versions/{version_num}/publish", response_model=ApiResponse[PromptVersionInfo], summary="发布指定版本")
async def publish_version(
    template_id: int,
    version_num: int,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    _: SysUser = Depends(require_permissions("ai:prompt:publish")),
):
    svc = PromptService(db, redis)
    version = await svc.publish_version(template_id, version_num)
    return ok(PromptVersionInfo.model_validate(version))


@router.post("/{template_id}/versions/{version_num}/rollback", response_model=ApiResponse[PromptTemplateInfo], summary="回滚到指定版本")
async def rollback_version(
    template_id: int,
    version_num: int,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    _: SysUser = Depends(require_permissions("ai:prompt:publish")),
):
    svc = PromptService(db, redis)
    tmpl = await svc.rollback(template_id, version_num)
    return ok(PromptTemplateInfo.model_validate(tmpl))


@router.post("/{template_id}/render", response_model=ApiResponse[dict], summary="预览渲染效果")
async def render_template(
    template_id: int,
    data: PromptRenderRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    _: SysUser = Depends(get_current_user),
):
    svc = PromptService(db, redis)
    rendered = await svc.render(template_id, data.variables, data.version)
    return ok({"rendered": rendered})
