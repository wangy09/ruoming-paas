"""
若茗 PaaS - 对话历史服务层
Author: ruoming
"""
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.conversation.models import AiConversation, AiMessage
from app.core.utils.pagination import PageParams


class ConversationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_list(
        self,
        user_id: int,
        agent_id: int | None,
        params: PageParams,
    ) -> tuple[list[AiConversation], int]:
        stmt = (
            select(AiConversation)
            .where(AiConversation.is_deleted == False)
            .where(AiConversation.user_id == user_id)
        )
        if agent_id is not None:
            stmt = stmt.where(AiConversation.agent_id == agent_id)

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiConversation.last_msg_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def get_messages(
        self, conversation_id: int, user_id: int, params: PageParams
    ) -> tuple[list[AiMessage], int]:
        """返回对话的历史消息，验证归属关系"""
        conv = await self.db.get(AiConversation, conversation_id)
        if not conv or conv.is_deleted or conv.user_id != user_id:
            return [], 0

        stmt = (
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
        )
        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiMessage.created_at.asc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def create_conversation(
        self,
        user_id: int,
        tenant_id: int | None,
        agent_id: int | None = None,
        workflow_id: int | None = None,
        title: str | None = None,
    ) -> AiConversation:
        conv = AiConversation(
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            workflow_id=workflow_id,
            title=title,
        )
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        model_config_id: int | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        tool_calls: dict | None = None,
        tool_results: dict | None = None,
    ) -> AiMessage:
        msg = AiMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_config_id=model_config_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            tool_results=tool_results,
        )
        self.db.add(msg)

        # 更新对话统计
        await self.db.execute(
            update(AiConversation)
            .where(AiConversation.id == conversation_id)
            .values(
                message_count=AiConversation.message_count + 1,
                last_msg_at=func.now(),
                # 首条用户消息自动设为标题（截取 50 字）
            )
        )
        await self.db.flush()
        return msg

    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        conv = await self.db.get(AiConversation, conversation_id)
        if not conv or conv.is_deleted or conv.user_id != user_id:
            return False
        conv.is_deleted = True
        await self.db.commit()
        return True
