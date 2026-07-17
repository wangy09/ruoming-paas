"""
若茗 PaaS - 配置中心路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_user_optional, require_permissions
from app.core.exceptions import NotFoundException
from app.core.response import ok, paged
from app.database import get_db
from app.modules.config_center.models import SysConfig
from app.modules.user.models import SysUser
from app.modules.config_center.schemas import (
    ConfigCacheClearResult,
    ConfigCreate,
    ConfigExportOut,
    ConfigImportIn,
    ConfigImportResult,
    ConfigOut,
    ConfigUpdate,
    PublicConfigOut,
)
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
        user_id=current_user.id,
        public_only=True,
    )
    return ok(data=values)


@router.get("/public", summary="公开配置列表")
async def get_public_configs(
    keys: list[str] = Query(default=[], description="配置键列表，为空时返回当前层级全部公开配置"),
    category: str | None = Query(None, description="配置分类"),
    app_key: str | None = Query(None, description="模块标识"),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser | None = Depends(get_current_user_optional),
):
    """只返回 is_public=true 且未加密、已启用的配置，供前端安全下发。"""
    svc = ConfigCenterService(db)
    tenant_id = current_user.tenant_id if current_user else None
    user_id = current_user.id if current_user else None
    if keys:
        values = await svc.get_merged(
            keys=keys,
            tenant_id=tenant_id,
            app_key=app_key,
            user_id=user_id,
            public_only=True,
        )
        return ok(data=values)

    items = await svc.list_by_scope(
        scope="tenant" if tenant_id else "global",
        tenant_id=tenant_id,
        app_key=app_key,
        category=category,
        is_public=True,
        is_encrypted=False,
        status=1,
    )
    return ok(data=[PublicConfigOut(
        config_key=i.config_key,
        config_val=i.config_val,
        val_type=i.val_type,
        category=i.category,
        label=i.label,
    ) for i in items])


@router.get("", summary="配置列表")
async def list_configs(
    scope: str = Query("global", description="层级：global/tenant/app/user"),
    app_key: str | None = Query(None),
    category: str | None = Query(None),
    keyword: str | None = Query(None),
    is_public: bool | None = Query(None),
    is_encrypted: bool | None = Query(None),
    status: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:list")),
):
    svc = ConfigCenterService(db)
    tenant_id = None if scope == "global" else current_user.tenant_id
    items = await svc.list_by_scope(
        scope=scope,
        tenant_id=tenant_id,
        app_key=app_key,
        category=category,
        keyword=keyword,
        is_public=is_public,
        is_encrypted=is_encrypted,
        status=status,
    )
    return ok(data=[ConfigOut.model_validate(svc.to_output(i)) for i in items])


@router.get("/export", summary="导出配置")
async def export_configs(
    scope: str = Query("global", description="层级：global/tenant/app/user"),
    app_key: str | None = Query(None),
    category: str | None = Query(None),
    keyword: str | None = Query(None),
    is_public: bool | None = Query(None),
    is_encrypted: bool | None = Query(None),
    status: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:list")),
):
    """导出当前筛选条件下的配置。加密配置不导出明文。"""
    svc = ConfigCenterService(db)
    tenant_id = None if scope == "global" else current_user.tenant_id
    items = await svc.export_items(
        scope=scope,
        tenant_id=tenant_id,
        app_key=app_key,
        category=category,
        keyword=keyword,
        is_public=is_public,
        is_encrypted=is_encrypted,
        status=status,
    )
    return ok(data=ConfigExportOut(items=[ConfigOut.model_validate(i) for i in items]))


@router.post("/import", summary="导入配置")
async def import_configs(
    body: ConfigImportIn,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:create", "config:update")),
):
    """批量导入配置。默认跳过已存在配置，可选择覆盖。"""
    svc = ConfigCenterService(db)
    result = await svc.import_items(
        [item.model_dump() for item in body.items],
        overwrite=body.overwrite,
        tenant_id=current_user.tenant_id,
        changed_by=current_user.id,
    )
    return ok(data=ConfigImportResult(**result))


@router.post("/cache/clear", summary="清理配置缓存")
async def clear_config_cache(
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:update")),
):
    """清理 config:merged:* 合并配置缓存。"""
    svc = ConfigCenterService(db)
    cleared = await svc.clear_merged_cache()
    return ok(data=ConfigCacheClearResult(cleared=cleared), message="配置缓存已清理")


@router.post("/refresh", summary="刷新运行时配置")
async def refresh_runtime_configs(
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:update")),
):
    """刷新并重新初始化所有运行时配置（限流、多租户等），确保配置项分类和值正确。"""
    from app.modules.config_center.runtime import ensure_runtime_configs
    from app.core.rate_limit_config import invalidate_rate_limit_cache
    from app.core.multi_tenant import invalidate_multi_tenant_cache

    await ensure_runtime_configs(db)
    await invalidate_rate_limit_cache()
    await invalidate_multi_tenant_cache()
    return ok(message="运行时配置已刷新，限流和多租户缓存已失效")


@router.post("", summary="创建配置项")
async def create_config(
    body: ConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:create")),
):
    svc = ConfigCenterService(db)
    tenant_id = None if body.scope == "global" else current_user.tenant_id
    obj = await svc.set(
        config_key=body.config_key,
        config_val=body.config_val or "",
        scope=body.scope,
        tenant_id=tenant_id,
        app_key=body.app_key,
        user_id=body.user_id,
        val_type=body.val_type,
        is_encrypted=body.is_encrypted,
        category=body.category,
        config_type=body.config_type,
        default_value=body.default_value,
        options=body.options,
        required=body.required,
        regex=body.regex,
        min_value=body.min_value,
        max_value=body.max_value,
        sort=body.sort,
        status=body.status,
        label=body.label,
        description=body.description,
        is_public=body.is_public,
        changed_by=current_user.id,
    )
    return ok(data=ConfigOut.model_validate(svc.to_output(obj)))


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
        where_clause += " AND h.config_key = :config_key"
        params["config_key"] = config_key

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM sys_config_history h {where_clause}"),
        params,
    )
    total = count_result.scalar_one_or_none() or 0

    data_result = await db.execute(
        text(
            "SELECT h.*, COALESCE(u.nickname, u.username) AS changed_by_name "
            f"FROM sys_config_history h LEFT JOIN sys_user u ON u.id = h.changed_by {where_clause} "
            "ORDER BY h.changed_at DESC OFFSET :offset LIMIT :limit"
        ),
        params,
    )
    rows = [dict(r._mapping) for r in data_result]

    return paged(items=rows, total=total, page=page, page_size=page_size)


@router.put("/{config_id}", summary="更新配置项")
async def update_config(
    config_id: int,
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:update")),
):
    from sqlalchemy import select

    result = await db.execute(
        select(SysConfig).where(SysConfig.id == config_id).where(SysConfig.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundException("配置项不存在")

    svc = ConfigCenterService(db)
    next_val = body.config_val if body.config_val is not None else ("" if obj.is_encrypted else (obj.config_val or ""))
    keep_encrypted_value = obj.is_encrypted and (body.config_val is None or body.config_val == "")
    updated = await svc.set(
        config_key=obj.config_key,
        config_val=next_val,
        scope=obj.scope,
        tenant_id=obj.tenant_id,
        app_key=obj.app_key,
        user_id=obj.user_id,
        val_type=body.val_type if body.val_type is not None else obj.val_type,
        is_encrypted=body.is_encrypted if body.is_encrypted is not None else obj.is_encrypted,
        category=body.category if body.category is not None else obj.category,
        config_type=body.config_type if body.config_type is not None else obj.config_type,
        default_value=body.default_value if body.default_value is not None else obj.default_value,
        options=body.options if body.options is not None else obj.options,
        required=body.required if body.required is not None else obj.required,
        regex=body.regex if body.regex is not None else obj.regex,
        min_value=body.min_value if body.min_value is not None else obj.min_value,
        max_value=body.max_value if body.max_value is not None else obj.max_value,
        sort=body.sort if body.sort is not None else obj.sort,
        status=body.status if body.status is not None else obj.status,
        label=body.label if body.label is not None else obj.label,
        description=body.description if body.description is not None else obj.description,
        is_public=body.is_public if body.is_public is not None else obj.is_public,
        changed_by=current_user.id,
        keep_encrypted_value=keep_encrypted_value,
    )
    return ok(data=ConfigOut.model_validate(svc.to_output(updated)))


@router.delete("/{config_id}", summary="删除配置项")
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("config:delete")),
):
    from sqlalchemy import select

    result = await db.execute(
        select(SysConfig).where(SysConfig.id == config_id).where(SysConfig.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundException("配置项不存在")

    svc = ConfigCenterService(db)
    await svc.delete(
        config_key=obj.config_key,
        scope=obj.scope,
        tenant_id=obj.tenant_id,
        app_key=obj.app_key,
        user_id=obj.user_id,
        changed_by=current_user.id,
    )
    return ok(message="删除成功")
