"""
若茗 PaaS - 对话历史路由
/api/v1/ai/conversations
Author: ruoming
"""
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.conversation.schemas import ConversationInfo, MessageInfo
from app.ai.conversation.service import ConversationService
from app.ai.llm.providers.base import ChatMessage
from app.ai.llm.schemas import ChatRequest
from app.ai.llm.service import LLMService
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundException
from app.core.rate_limit import limiter, get_user_key
from app.core.response import ApiResponse, PageData, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ai/conversations", tags=["AI-对话历史"])


@router.get("", response_model=ApiResponse[PageData[ConversationInfo]], summary="对话列表")
async def list_conversations(
    agent_id: int | None = Query(None, description="按 Agent 过滤"),
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = ConversationService(db)
    items, total = await svc.get_list(current_user.id, agent_id, page_params)
    return paged(items=[ConversationInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


@router.get("/{conversation_id}/messages", response_model=ApiResponse[PageData[MessageInfo]], summary="消息列表")
async def list_messages(
    conversation_id: int,
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = ConversationService(db)
    items, total = await svc.get_messages(conversation_id, current_user.id, page_params)
    return paged(items=[MessageInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


@router.delete("/{conversation_id}", response_model=ApiResponse, summary="删除对话")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = ConversationService(db)
    ok_flag = await svc.delete_conversation(conversation_id, current_user.id)
    if not ok_flag:
        raise NotFoundException("对话不存在或无权操作")
    return ok(message="删除成功")


@router.post("/chat", summary="AI 对话（支持流式 SSE）")
@limiter.limit("30/minute", key_func=get_user_key)
async def chat(
    data: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """
    支持流式（SSE）和非流式两种模式。
    - stream=true：返回 text/event-stream
    - stream=false：返回普通 JSON
    """
    conv_svc = ConversationService(db)
    llm_svc = LLMService()

    # 解析或创建对话
    if data.conversation_id:
        from app.ai.conversation.models import AiConversation
        conv = await db.get(AiConversation, data.conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise NotFoundException("对话不存在")
    else:
        first_msg = data.messages[-1].get("content", "")[:50] if data.messages else "新对话"
        conv = await conv_svc.create_conversation(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            title=first_msg,
        )

    # 构建 ChatMessage 列表
    messages = [
        ChatMessage(role=m["role"], content=m["content"])
        for m in data.messages
    ]

    if data.stream:
        # 流式 SSE 响应
        async def _generate() -> AsyncGenerator[str, None]:
            start_ms = int(time.time() * 1000)
            full_content = ""
            try:
                gen = await llm_svc.stream_chat(
                    messages=messages,
                    model_config_id=data.model_config_id,
                    db=db,
                    temperature=data.temperature,
                    max_tokens=data.max_tokens,
                )
                async for chunk in gen:
                    full_content += chunk
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                latency_ms = int(time.time() * 1000) - start_ms
                # 保存消息记录（非阻塞，允许失败不影响响应）
                try:
                    await conv_svc.add_message(
                        conversation_id=conv.id,
                        role="user",
                        content=messages[-1].content if messages else "",
                    )
                    await conv_svc.add_message(
                        conversation_id=conv.id,
                        role="assistant",
                        content=full_content,
                        latency_ms=latency_ms,
                    )
                    await db.commit()
                except Exception as e:
                    logger.warning("conversation_save_failed", error=str(e))

        return StreamingResponse(_generate(), media_type="text/event-stream")
    else:
        # 非流式
        start_ms = int(time.time() * 1000)
        result = await llm_svc.chat(
            messages=messages,
            model_config_id=data.model_config_id,
            db=db,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            user_id=current_user.id,
            conversation_id=conv.id,
        )
        latency_ms = int(time.time() * 1000) - start_ms

        await conv_svc.add_message(
            conversation_id=conv.id,
            role="user",
            content=messages[-1].content if messages else "",
        )
        await conv_svc.add_message(
            conversation_id=conv.id,
            role="assistant",
            content=result.content,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            latency_ms=latency_ms,
        )
        await db.commit()

        return ok({
            "content": result.content,
            "conversation_id": conv.id,
            "total_tokens": result.total_tokens,
            "latency_ms": latency_ms,
        })
