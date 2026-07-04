"""
若茗 PaaS - 仪表盘路由
Author: ruoming
"""
import json
from typing import Literal
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator

from app.core.deps import get_current_user
from app.core.error_codes import SysErrCode
from app.core.exceptions import BusinessException
from app.core.redis import get_redis
from app.core.response import ApiResponse, ok
from app.database import get_db

from app.modules.config_center.service import ConfigCenterService
from app.modules.permission.models import SysPermission
from app.modules.permission.service import PermissionService
router = APIRouter()

DASHBOARD_PREFERENCES_KEY = "dashboard.preferences"
DEFAULT_WIDGETS = {
    "stats": True,
    "quick_entries": True,
    "todos": True,
    "messages": True,
    "notices": True,
    "workbench": True,
}
MAX_QUICK_ENTRIES = 12


class DashboardQuickEntry(BaseModel):
    """用户自定义常用入口"""

    title: str = Field(..., min_length=1, max_length=64)
    path: str = Field(..., min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=32)
    desc: str | None = Field(default=None, max_length=128)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("入口路径必须以 / 开头")
        return value


class DashboardPreferences(BaseModel):
    """当前用户首页偏好"""

    template_type: Literal["auto", "platform", "tenant", "developer", "personal"] = "auto"
    widgets: dict[str, bool] = Field(default_factory=lambda: DEFAULT_WIDGETS.copy(), description="组件显示配置")
    quick_entries: list[DashboardQuickEntry] = Field(default_factory=list, max_length=MAX_QUICK_ENTRIES, description="我的常用入口")


class DashboardPreferencesOut(BaseModel):
    """首页偏好输出"""

    preferences: DashboardPreferences
    source: Literal["user", "default"] = "default"


def _normalize_preferences(raw: str | None) -> DashboardPreferences:
    if not raw:
        return DashboardPreferences()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return DashboardPreferences()
    prefs = DashboardPreferences.model_validate(data if isinstance(data, dict) else {})
    prefs.widgets = {**DEFAULT_WIDGETS, **(prefs.widgets or {})}
    prefs.quick_entries = _dedupe_quick_entries(prefs.quick_entries)
    return prefs


def _dedupe_quick_entries(entries: list[DashboardQuickEntry]) -> list[DashboardQuickEntry]:
    seen: set[str] = set()
    result: list[DashboardQuickEntry] = []
    for entry in entries:
        if entry.path in seen:
            continue
        seen.add(entry.path)
        result.append(entry)
        if len(result) >= MAX_QUICK_ENTRIES:
            break
    return result


def _collect_menu_paths(menus: list[dict]) -> set[str]:
    paths: set[str] = set()
    for menu in menus:
        path = menu.get("path")
        if isinstance(path, str) and path.startswith("/"):
            paths.add(path)
        children = menu.get("children") or []
        if children:
            paths.update(_collect_menu_paths(children))
    return paths


async def _allowed_menu_paths(current_user, db: AsyncSession, redis: Redis) -> set[str]:
    svc = PermissionService(db, redis)
    if current_user.is_superplatform:
        data = await svc.get_all_menus()
        return _collect_menu_paths(data.get("menus") or [])
    else:
        codes = await svc.get_user_permission_codes(current_user.id)
        if not codes:
            return set()

    result = await db.execute(
        select(SysPermission.path).where(
            SysPermission.code.in_(codes),
            SysPermission.perm_type == "menu",
            SysPermission.is_visible == True,  # noqa: E712
            SysPermission.is_deleted == False,  # noqa: E712
        )
    )
    return {path for path in result.scalars().all() if path}


async def _validate_quick_entries(
    preferences: DashboardPreferences,
    current_user,
    db: AsyncSession,
    redis: Redis,
) -> DashboardPreferences:
    allowed_paths = await _allowed_menu_paths(current_user, db, redis)
    invalid_paths = [entry.path for entry in preferences.quick_entries if entry.path not in allowed_paths]
    if invalid_paths:
        raise BusinessException(
            code=SysErrCode.FORBIDDEN,
            message=f"常用入口无访问权限：{', '.join(invalid_paths[:3])}",
            http_status=403,
        )
    preferences.quick_entries = _dedupe_quick_entries(preferences.quick_entries)
    return preferences


@router.get(
    "/stats",
    response_model=ApiResponse,
    summary="仪表盘统计",
)
async def get_dashboard_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取仪表盘统计数据"""
    from app.modules.user.models import SysUser
    from app.modules.tenant.models import SysTenant
    from sqlalchemy import select, func

    tenant_id = None if current_user.is_superplatform else current_user.tenant_id

    # 1. 总用户数
    user_query = select(func.count(SysUser.id)).where(
        SysUser.is_deleted == False,
        SysUser.status == 1,
    )
    if tenant_id:
        user_query = user_query.where(SysUser.tenant_id == tenant_id)
    result = await db.execute(user_query)
    total_users = result.scalar() or 0

    # 2. 活跃租户数（仅平台管理员可见）
    active_tenants = 0
    if current_user.is_superplatform:
        tenant_query = select(func.count(SysTenant.id)).where(
            SysTenant.is_deleted == False,
            SysTenant.status == 1,
        )
        result = await db.execute(tenant_query)
        active_tenants = result.scalar() or 0

    # 3. AI 调用次数（从对话记录统计）
    today_calls = 0
    today_tokens = 0
    try:
        from app.ai.conversation.models import Conversation
        from datetime import datetime

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conv_query = select(func.count(Conversation.id)).where(
            Conversation.created_at >= today,
        )
        if tenant_id:
            conv_query = conv_query.where(Conversation.tenant_id == tenant_id)
        result = await db.execute(conv_query)
        today_calls = result.scalar() or 0
        today_tokens = today_calls * 500
    except Exception:
        pass

    return ok({
        "total_users": total_users,
        "active_tenants": active_tenants,
        "today_calls": today_calls,
        "today_tokens": today_tokens,
    })


@router.get(
    "/preferences",
    response_model=ApiResponse,
    summary="获取我的首页偏好",
)
async def get_dashboard_preferences(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当前用户首页偏好。底层复用配置中心 user > tenant > global 覆盖能力。"""
    svc = ConfigCenterService(db)
    own_value = await svc.get(
        DASHBOARD_PREFERENCES_KEY,
        scope="user",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    source = "user" if own_value else "default"
    values = await svc.get_merged(
        keys=[DASHBOARD_PREFERENCES_KEY],
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        public_only=False,
    )
    prefs = _normalize_preferences(values.get(DASHBOARD_PREFERENCES_KEY))
    return ok(data=DashboardPreferencesOut(preferences=prefs, source=source).model_dump())


@router.put(
    "/preferences",
    response_model=ApiResponse,
    summary="保存我的首页偏好",
)
async def update_dashboard_preferences(
    body: DashboardPreferences,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    """保存当前用户首页偏好，只写入 user scope，不影响其他用户。"""
    svc = ConfigCenterService(db)
    body.widgets = {**DEFAULT_WIDGETS, **(body.widgets or {})}
    body = await _validate_quick_entries(body, current_user, db, redis)
    await svc.set(
        config_key=DASHBOARD_PREFERENCES_KEY,
        config_val=body.model_dump_json(),
        scope="user",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        val_type="json",
        category="dashboard",
        config_type="json",
        label="首页偏好",
        description="当前用户首页模板与组件显示配置",
        is_public=False,
        changed_by=current_user.id,
    )
    return ok(data=DashboardPreferencesOut(preferences=body, source="user").model_dump(), message="首页偏好已保存")


@router.delete(
    "/preferences",
    response_model=ApiResponse,
    summary="重置我的首页偏好",
)
async def reset_dashboard_preferences(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """删除当前用户首页偏好，恢复系统默认自动首页。"""
    svc = ConfigCenterService(db)
    await svc.delete(
        DASHBOARD_PREFERENCES_KEY,
        scope="user",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        changed_by=current_user.id,
    )
    return ok(
        data=DashboardPreferencesOut(preferences=DashboardPreferences(), source="default").model_dump(),
        message="首页偏好已重置",
    )
