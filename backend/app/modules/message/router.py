"""
若茗 PaaS - 消息中心 API
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.response import ApiResponse, ok
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.message.schemas import MessageInfo, NoticeCreate, NoticeInfo, NoticeUpdate
from app.modules.message.service import MessageService
from app.modules.user.models import SysUser

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# 平台公告管理
# ══════════════════════════════════════════════════════════════

@router.get("/notices", response_model=ApiResponse, summary="公告列表")
async def list_notices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:view"))],
    page_params: Annotated[PageParams, Depends()],
    keyword: str | None = Query(None, description="标题关键字"),
    status: int | None = Query(None, description="状态：0草稿 1已发布"),
    target_type: str | None = Query(None, description="投放范围：all/dept/user"),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    data = await svc.list_notices(page_params, keyword=keyword, status=status, target_type=target_type)
    data["items"] = [NoticeInfo.model_validate(item) for item in data["items"]]
    return ok(data)


@router.post("/notices", response_model=ApiResponse[NoticeInfo], summary="创建公告")
async def create_notice(
    body: NoticeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:create"))],
) -> ApiResponse[NoticeInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    notice = await svc.create_notice(body, current_user)
    await db.commit()
    await db.refresh(notice)
    return ok(NoticeInfo.model_validate(notice), message="创建成功")


@router.get("/notices/{notice_id}", response_model=ApiResponse[NoticeInfo], summary="公告详情")
async def get_notice(
    notice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:view"))],
) -> ApiResponse[NoticeInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    notice = await svc.get_notice(notice_id)
    return ok(NoticeInfo.model_validate(notice))


@router.put("/notices/{notice_id}", response_model=ApiResponse[NoticeInfo], summary="编辑公告")
async def update_notice(
    notice_id: int,
    body: NoticeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:update"))],
) -> ApiResponse[NoticeInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    notice = await svc.update_notice(notice_id, body)
    await db.commit()
    await db.refresh(notice)
    return ok(NoticeInfo.model_validate(notice), message="保存成功")


@router.delete("/notices/{notice_id}", response_model=ApiResponse, summary="删除公告")
async def delete_notice(
    notice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:delete"))],
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    await svc.delete_notice(notice_id)
    await db.commit()
    return ok(message="删除成功")


@router.post("/notices/{notice_id}/publish", response_model=ApiResponse[NoticeInfo], summary="发布公告")
async def publish_notice(
    notice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("message:notice:publish"))],
) -> ApiResponse[NoticeInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = MessageService(db, tenant_id)
    notice = await svc.get_notice(notice_id)
    notice = await svc.publish_notice(notice, current_user)
    await db.commit()
    await db.refresh(notice)
    return ok(NoticeInfo.model_validate(notice), message="发布成功")


# ══════════════════════════════════════════════════════════════
# 我的消息
# ══════════════════════════════════════════════════════════════

@router.get("/inbox", response_model=ApiResponse, summary="我的消息列表")
async def list_my_messages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    is_read: bool | None = Query(None, description="是否已读"),
) -> ApiResponse:
    svc = MessageService(db)
    data = await svc.list_user_messages(current_user.id, page_params, is_read=is_read)
    data["items"] = [MessageInfo.model_validate(item) for item in data["items"]]
    return ok(data)


@router.get("/inbox/unread", response_model=ApiResponse, summary="未读消息摘要")
async def unread_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
) -> ApiResponse:
    svc = MessageService(db)
    data = await svc.unread_summary(current_user.id)
    latest = data.get("latest")
    data["latest"] = MessageInfo.model_validate(latest) if latest else None
    return ok(data)


@router.post("/inbox/{message_id}/read", response_model=ApiResponse[MessageInfo], summary="标记消息已读")
async def mark_read(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
) -> ApiResponse[MessageInfo]:
    svc = MessageService(db)
    msg = await svc.mark_read(message_id, current_user.id)
    await db.commit()
    await db.refresh(msg)
    return ok(MessageInfo.model_validate(msg))


@router.post("/inbox/read-all", response_model=ApiResponse, summary="全部标记已读")
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
) -> ApiResponse:
    svc = MessageService(db)
    count = await svc.mark_all_read(current_user.id)
    await db.commit()
    return ok({"updated": count})


@router.delete("/inbox/{message_id}", response_model=ApiResponse, summary="删除我的消息")
async def delete_my_message(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
) -> ApiResponse:
    svc = MessageService(db)
    await svc.delete_user_message(message_id, current_user.id)
    await db.commit()
    return ok(message="删除成功")
