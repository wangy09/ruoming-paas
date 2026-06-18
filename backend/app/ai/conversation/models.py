"""
若茗 PaaS - AI 对话历史 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.database import Base


class AiConversation(BaseModel):
    """
    AI 对话主表（ai_conversation）。
    一个 conversation 对应一次完整的人机对话会话。
    """

    __tablename__ = "ai_conversation"

    title: Mapped[str | None] = mapped_column(nullable=True, comment="对话标题（首条消息自动截取）")
    agent_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="关联 Agent ID（直接对话时为 NULL）"
    )
    workflow_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="关联工作流 ID"
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="发起用户 ID")
    message_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="消息总条数"
    )
    last_msg_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后一条消息时间"
    )


class AiMessage(Base):
    """
    AI 消息表（ai_message）。
    记录每一条对话消息，含 Token 统计和延迟数据，不继承 BaseModel（不需要软删除、租户字段）。
    """

    __tablename__ = "ai_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="所属对话 ID"
    )
    role: Mapped[str] = mapped_column(
        nullable=False, comment="角色：user / assistant / system / tool"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="工具调用信息")
    tool_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="工具调用结果")
    model_config_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="使用的模型配置 ID")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输入 Token 数")
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输出 Token 数")
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总 Token 数")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="推理延迟（毫秒）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", comment="创建时间"
    )


class AiCallLog(Base):
    """
    AI 调用日志表（ai_call_log）。
    记录每次 LLM API 调用的 Token 消耗、延迟、费用估算，用于计费和监控。
    """

    __tablename__ = "ai_call_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    call_type: Mapped[str | None] = mapped_column(
        nullable=True, comment="调用类型：chat / agent / workflow / embed"
    )
    model_config_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="模型配置 ID")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="调用用户 ID")
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联对话 ID")
    session_id: Mapped[str | None] = mapped_column(nullable=True, comment="会话 ID")
    workflow_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联工作流执行 ID")
    request_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="请求 Token 数")
    response_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应 Token 数")
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总 Token 数")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="延迟（毫秒）")
    status: Mapped[str | None] = mapped_column(
        nullable=True, comment="状态：success / error / timeout"
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    cost_estimate: Mapped[float | None] = mapped_column(
        Numeric(10, 6), nullable=True, comment="预估费用（元）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", comment="记录时间"
    )
