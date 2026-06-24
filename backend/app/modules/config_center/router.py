"""
若茗 PaaS - 配置中心路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.response import PageData, ok, paged
from app.database import get_db
from app.modules.user.models import SysUser
from app.modules.config_center.schemas import ConfigCreate, ConfigOut, ConfigUpdate
from app.modules.config_center.service import ConfigCenterService

router = APIRouter(prefix="/config-center", tags=["配置中心"])


@router.get("/merged", summary="合并查询配置（四级覆盖）")
async def get_merged_config(
    keys: list[str] = Query(..., description="配置键列表"),
    app_key: str | None = Query(None, description="模块标识"),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """按四级优先级合并返回配置。只返回 is_public=true 的配置（前端安全下发）。"""
    svc = ConfigCenterService(db)
    values = await svc.get_merged(
        keys=keys,
        tenant_id=current_user.tenant_id,
        app_key=app_key,
        user_id=current_user.user_id,
    )
    return ok(data=values)


@router.get("", summary="配置列表")
async def list_configs(
    scope: str = Query("tenant", description="层级：global/tenant/app/user"),
    app_key: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:list")),
):
    svc = ConfigCenterService(db)
    items = await svc.list_by_scope(
        scope=scope,
        tenant_id=current_user.tenant_id,
        app_key=app_key,
    )
    return ok(data=[ConfigOut.model_validate(i) for i in items])


@router.post("", summary="创建配置项")
async def create_config(
    body: ConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:create")),
):
    svc = ConfigCenterService(db)
    obj = await svc.set(
        config_key=body.config_key,
        config_val=body.config_val or "",
        scope=body.scope,
        tenant_id=body.scope != "global" and current_user.tenant_id or None,
        app_key=body.app_key,
        user_id=body.user_id,
        val_type=body.val_type,
        is_encrypted=body.is_encrypted,
        label=body.label,
        description=body.description,
        is_public=body.is_public,
        changed_by=current_user.user_id,
    )
    return ok(data=ConfigOut.model_validate(obj))


@router.put("/{config_id}", summary="更新配置项")
async def update_config(
    config_id: int,
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:update")),
):
    from sqlalchemy import select
    from app.modules.config_center.models import SysConfig

    result = await db.execute(
        select(SysConfig).where(SysConfig.id == config_id).where(SysConfig.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("配置项不存在")

    svc = ConfigCenterService(db)
    updated = await svc.set(
        config_key=obj.config_key,
        config_val=body.config_val if body.config_val is not None else (obj.config_val or ""),
        scope=obj.scope,
        tenant_id=obj.tenant_id,
        app_key=obj.app_key,
        user_id=obj.user_id,
        val_type=obj.val_type,
        is_encrypted=obj.is_encrypted,
        label=body.label if body.label is not None else obj.label,
        description=body.description if body.description is not None else obj.description,
        is_public=body.is_public if body.is_public is not None else obj.is_public,
        changed_by=current_user.user_id,
    )
    return ok(data=ConfigOut.model_validate(updated))


@router.delete("/{config_id}", summary="删除配置项")
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:delete")),
):
    from sqlalchemy import select
    from app.modules.config_center.models import SysConfig

    result = await db.execute(
        select(SysConfig).where(SysConfig.id == config_id).where(SysConfig.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("配置项不存在")

    svc = ConfigCenterService(db)
    await svc.delete(
        config_key=obj.config_key,
        scope=obj.scope,
        tenant_id=obj.tenant_id,
        app_key=obj.app_key,
        user_id=obj.user_id,
    )
    return ok(message="删除成功")


@router.get("/history", summary="配置变更历史")
async def get_config_history(
    config_key: str | None = Query(None, description="按配置键筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:list")),
):
    """查询配置变更历史（审计用）"""
    from sqlalchemy import text

    where_clause = "WHERE 1=1"
    params: dict = {"offset": (page - 1) * page_size, "limit": page_size}
    if config_key:
        where_clause += " AND config_key = :config_key"
        params["config_key"] = config_key

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM sys_config_history {where_clause}"),
        params,
    )
    total = count_result.scalar_one_or_none() or 0

    data_result = await db.execute(
        text(
            f"SELECT * FROM sys_config_history {where_clause} "
            "ORDER BY changed_at DESC OFFSET :offset LIMIT :limit"
        ),
        params,
    )
    rows = [dict(r._mapping) for r in data_result]

    return paged(items=rows, total=total, page=page, page_size=page_size)
