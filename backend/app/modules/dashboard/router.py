"""
若茗 PaaS - 仪表盘路由
Author: ruoming
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ApiResponse, ok
from app.database import get_db

router = APIRouter()


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
