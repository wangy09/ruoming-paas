"""
若茗 PaaS - LLM 模型管理路由
/api/v1/ai/models
Author: ruoming
"""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.models import AiModelConfig
from app.ai.llm.schemas import (
    ChatRequest,
    ModelConfigCreate,
    ModelConfigInfo,
    ModelConfigUpdate,
    ModelTestResult,
)
from app.ai.llm.service import LLMService
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import NotFoundException
from app.core.response import ApiResponse, PageData, ok, created, paged, error
from app.core.security import encrypt_value
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/models", tags=["AI-模型管理"])


def _to_info(config: AiModelConfig) -> ModelConfigInfo:
    """将 ORM 模型转换为 schema，并补充 has_api_key 字段"""
    info = ModelConfigInfo.model_validate(config)
    info.has_api_key = bool(config.api_key and config.api_key.strip())
    return info


@router.get("", response_model=ApiResponse[PageData[ModelConfigInfo]], summary="模型配置列表")
async def list_model_configs(
    page_params: PageParams = Depends(),
    model_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:model:list")),
):
    """
    模型配置列表。
    model_type 可选过滤：embed（向量嵌入模型）/ rerank（重排序模型）/ default（默认对话模型）
    """
    stmt = (
        select(AiModelConfig)
        .where(AiModelConfig.is_deleted == False)
        .order_by(AiModelConfig.created_at.desc())
    )
    total_stmt = select(AiModelConfig).where(AiModelConfig.is_deleted == False)

    # 按模型用途过滤
    if model_type == "embed":
        stmt = stmt.where(AiModelConfig.is_embed == True)
        total_stmt = total_stmt.where(AiModelConfig.is_embed == True)
    elif model_type == "rerank":
        stmt = stmt.where(AiModelConfig.is_rerank == True)
        total_stmt = total_stmt.where(AiModelConfig.is_rerank == True)
    elif model_type == "default":
        stmt = stmt.where(AiModelConfig.is_default == True)
        total_stmt = total_stmt.where(AiModelConfig.is_default == True)

    from sqlalchemy import func
    count_result = await db.execute(select(func.count()).select_from(total_stmt.subquery()))
    total = count_result.scalar_one()

    stmt = stmt.offset(page_params.offset).limit(page_params.page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return paged(items=[_to_info(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


@router.post("", response_model=ApiResponse[ModelConfigInfo], summary="添加模型配置", status_code=201)
async def create_model_config(
    data: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("ai:model:create")),
):
    # api_key 写入时自动加密
    encrypted_key = encrypt_value(data.api_key) if data.api_key else None

    config = AiModelConfig(
        name=data.name,
        provider=data.provider,
        model_id=data.model_id,
        api_key=encrypted_key,
        base_url=data.base_url,
        is_default=data.is_default,
        is_embed=data.is_embed,
        is_rerank=data.is_rerank,
        max_tokens=data.max_tokens,
        context_length=data.context_length,
        remark=data.remark,
        tenant_id=current_user.tenant_id,
    )

    # 若设置为默认，清除同类其他模型的 is_default
    if data.is_default and not data.is_embed:
        await db.execute(
            select(AiModelConfig)
            .where(AiModelConfig.is_default == True)
            .where(AiModelConfig.is_embed == False)
            .where(AiModelConfig.is_deleted == False)
        )
        # 用 update 语句批量清空（避免 N+1）
        from sqlalchemy import update
        await db.execute(
            update(AiModelConfig)
            .where(AiModelConfig.is_default == True)
            .where(AiModelConfig.is_embed == False)
            .values(is_default=False)
        )

    db.add(config)
    await db.commit()
    await db.refresh(config)
    return created(_to_info(config))


@router.put("/{config_id}", response_model=ApiResponse[ModelConfigInfo], summary="修改模型配置")
async def update_model_config(
    config_id: int,
    data: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:model:update")),
):
    config = await db.get(AiModelConfig, config_id)
    if not config or config.is_deleted:
        raise NotFoundException(f"模型配置 ID={config_id} 不存在")

    update_data = data.model_dump(exclude_unset=True)

    # api_key 更新时重新加密
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key"] = encrypt_value(update_data["api_key"])

    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    # 通知所有 Worker 失效该 Provider 缓存
    await LLMService.notify_config_changed(config_id)

    return ok(_to_info(config))


@router.delete("/{config_id}", response_model=ApiResponse, summary="删除模型配置")
async def delete_model_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:model:delete")),
):
    config = await db.get(AiModelConfig, config_id)
    if not config or config.is_deleted:
        raise NotFoundException(f"模型配置 ID={config_id} 不存在")

    config.is_deleted = True
    await db.commit()
    await LLMService.notify_config_changed(config_id)
    return ok(message="删除成功")


@router.post("/{config_id}/test", response_model=ApiResponse[ModelTestResult], summary="测试模型连通性")
async def test_model_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    config = await db.get(AiModelConfig, config_id)
    if not config or config.is_deleted:
        raise NotFoundException(f"模型配置 ID={config_id} 不存在")

    from app.ai.llm.service import LLMService
    provider = LLMService._build_provider(config)

    start = time.time()
    try:
        success = await provider.test_connection()
        latency_ms = int((time.time() - start) * 1000)
        return ok(ModelTestResult(success=success, latency_ms=latency_ms))
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return ok(ModelTestResult(success=False, latency_ms=latency_ms, error=str(e)))
