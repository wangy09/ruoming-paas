"""
若茗 PaaS - 对话历史服务层
Author: ruoming
"""
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.conversation.models import AiConversation, AiMessage, AiEntityMemory, AiKeyValueMemory
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

    async def cleanup_old_messages(self, conversation_id: int, max_messages: int = 500) -> int:
        """
        清理对话历史中超出限制的旧消息。
        保留最近 max_messages 条，删除更早的消息。
        返回删除的消息数量。
        """
        stmt = (
            select(AiMessage.id)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.created_at.asc())
        )
        all_ids = (await self.db.scalars(stmt)).all()
        if len(all_ids) <= max_messages:
            return 0

        to_delete = all_ids[: len(all_ids) - max_messages]
        await self.db.execute(
            delete(AiMessage).where(AiMessage.id.in_(to_delete))
        )
        await self.db.commit()
        return len(to_delete)

    async def get_entity_memory(self, conversation_id: int, query: str) -> list[AiEntityMemory]:
        """检索与查询相关的实体记忆"""
        from sqlalchemy import or_

        keywords = query.split()[:10]
        conditions = []
        for kw in keywords:
            conditions.append(AiEntityMemory.entity_name.ilike(f"%{kw}%"))
            conditions.append(AiEntityMemory.entity_value.ilike(f"%{kw}%"))

        if conditions:
            result = await self.db.execute(
                select(AiEntityMemory).where(
                    AiEntityMemory.conversation_id == conversation_id,
                    AiEntityMemory.is_deleted == False,
                    or_(*conditions),
                ).limit(10)
            )
            return result.scalars().all()
        return []

    async def set_kv_memory(self, conversation_id: int, key: str, value: str, description: str | None = None) -> AiKeyValueMemory:
        """设置键值记忆"""
        existing = await self.db.scalar(
            select(AiKeyValueMemory).where(
                AiKeyValueMemory.conversation_id == conversation_id,
                AiKeyValueMemory.key == key,
                AiKeyValueMemory.is_deleted == False,
            )
        )

        if existing:
            existing.value = value
            if description:
                existing.description = description
        else:
            existing = AiKeyValueMemory(
                conversation_id=conversation_id,
                key=key,
                value=value,
                description=description,
            )
            self.db.add(existing)

        await self.db.flush()
        return existing

    async def get_kv_memory(self, conversation_id: int, key: str) -> AiKeyValueMemory | None:
        """获取键值记忆"""
        return await self.db.scalar(
            select(AiKeyValueMemory).where(
                AiKeyValueMemory.conversation_id == conversation_id,
                AiKeyValueMemory.key == key,
                AiKeyValueMemory.is_deleted == False,
            )
        )

    async def delete_kv_memory(self, conversation_id: int, key: str) -> bool:
        """删除键值记忆"""
        kv = await self.get_kv_memory(conversation_id, key)
        if kv:
            kv.is_deleted = True
            await self.db.commit()
            return True
        return False
