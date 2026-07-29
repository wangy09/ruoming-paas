"""
若茗 PaaS - 对话历史 Pydantic Schema
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    agent_id: int | None
    workflow_id: int | None
    user_id: int
    message_count: int
    last_msg_at: datetime | None
    created_at: datetime

    # 前端兼容字段
    last_message_at: datetime | None = None


class MessageInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    tool_calls: dict | None
    tool_results: dict | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    created_at: datetime

    # 前端兼容字段
    token_count: int | None = None
