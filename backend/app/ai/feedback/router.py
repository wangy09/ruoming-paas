"""
若茗 PaaS - AI 反馈管理路由
/api/v1/ai/feedback
Author: ruoming
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.feedback.schemas import (
    FeedbackCreate,
    FeedbackInfo,
    FeedbackStats,
    FeedbackUpdate,
)
from app.ai.feedback.service import FeedbackService
from app.core.deps import get_current_user, require_permissions
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db, get_read_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/feedback", tags=["AI-反馈管理"])


# ── 用户端 ────────────────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[FeedbackInfo], summary="提交反馈")
async def create_feedback(
    data: FeedbackCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    """用户提交系统反馈（Bug报告、功能建议、使用问题等）"""
    svc = FeedbackService(db, current_user.tenant_id)
    feedback = await svc.create(
        user_id=current_user.id,
        data=data,
        tenant_id=current_user.tenant_id,
    )
    return created(data=FeedbackInfo.model_validate(feedback), message="反馈提交成功")


@router.get(
    "/me",
    response_model=ApiResponse[PageData[FeedbackInfo]],
    summary="我的反馈列表",
)
async def list_my_feedbacks(
    db: Annotated[AsyncSession, Depends(get_read_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
):
    """查看当前用户自己提交的反馈列表"""
    svc = FeedbackService(db)
    items, total = await svc.list_my_feedbacks(current_user.id, page_params)
    return paged(
        items=[FeedbackInfo.model_validate(i) for i in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


# ── 管理端 ────────────────────────────────────────────────────────────────────
# 注意：/stats 必须在 /{feedback_id} 之前注册，否则会被路径参数匹配


@router.get(
    "",
    response_model=ApiResponse[PageData[FeedbackInfo]],
    summary="反馈列表（管理后台）",
)
async def list_feedbacks(
    db: Annotated[AsyncSession, Depends(get_read_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("ai:feedback:view"))],
    page_params: Annotated[PageParams, Depends()],
    category: str | None = Query(None, pattern="^(bug|feature|usage|other)$", description="反馈分类"),
    severity: str | None = Query(None, pattern="^(low|medium|high|critical)$", description="严重程度"),
    status: str | None = Query(None, pattern="^(pending|resolved|ignored)$", description="处理状态"),
    agent_id: int | None = Query(None, description="按 Agent 过滤"),
    user_id: int | None = Query(None, description="按用户过滤"),
    start_time: str | None = Query(None, description="开始时间（ISO 8601）"),
    end_time: str | None = Query(None, description="结束时间（ISO 8601）"),
):
    """管理后台反馈列表，支持多维度筛选（join 用户名与 Agent 名称）"""
    svc = FeedbackService(db, None if current_user.is_superplatform else current_user.tenant_id)
    filters = {
        "category": category,
        "severity": severity,
        "status": status,
        "agent_id": agent_id,
        "user_id": user_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    items, total = await svc.list_feedbacks(filters, page_params)
    return paged(
        items=[FeedbackInfo.model_validate(i) for i in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.get(
    "/stats",
    response_model=ApiResponse[FeedbackStats],
    summary="反馈统计",
)
async def feedback_stats(
    db: Annotated[AsyncSession, Depends(get_read_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("ai:feedback:view"))],
    category: str | None = Query(None, pattern="^(bug|feature|usage|other)$", description="反馈分类"),
    severity: str | None = Query(None, pattern="^(low|medium|high|critical)$", description="严重程度"),
    status: str | None = Query(None, pattern="^(pending|resolved|ignored)$", description="状态筛选"),
    agent_id: int | None = Query(None, description="按 Agent 过滤"),
    user_id: int | None = Query(None, description="按用户过滤"),
    start_time: str | None = Query(None, description="开始时间（ISO 8601）"),
    end_time: str | None = Query(None, description="结束时间（ISO 8601）"),
):
    """反馈统计数据：汇总指标、每日趋势、分类分布"""
    svc = FeedbackService(db, None if current_user.is_superplatform else current_user.tenant_id)
    filters = {
        "category": category,
        "severity": severity,
        "status": status,
        "agent_id": agent_id,
        "user_id": user_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    result = await svc.stats(filters)
    return ok(data=result)


@router.put(
    "/{feedback_id}",
    response_model=ApiResponse[FeedbackInfo],
    summary="处理反馈",
)
async def update_feedback(
    feedback_id: int,
    data: FeedbackUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("ai:feedback:reply"))],
):
    """管理员处理反馈：更新状态、回复内容"""
    svc = FeedbackService(db, None if current_user.is_superplatform else current_user.tenant_id)
    feedback = await svc.update(feedback_id, data, current_user.id)
    return ok(data=FeedbackInfo.model_validate(feedback), message="处理成功")


@router.delete(
    "/{feedback_id}",
    response_model=ApiResponse,
    summary="删除反馈",
)
async def delete_feedback(
    feedback_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("ai:feedback:delete"))],
):
    """软删除反馈记录"""
    svc = FeedbackService(db, None if current_user.is_superplatform else current_user.tenant_id)
    await svc.delete(feedback_id)
    return ok(message="删除成功")
