"""
若茗 PaaS - AI 反馈管理 Pydantic Schemas
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    """提交系统反馈请求"""

    title: str = Field(..., min_length=5, max_length=200, description="反馈标题（5-200字）")
    category: str = Field(
        ..., pattern="^(bug|feature|usage|other)$",
        description="反馈分类：bug=Bug报告, feature=功能建议, usage=使用问题, other=其他"
    )
    content: str = Field(..., min_length=10, max_length=5000, description="详细反馈内容（10-5000字）")
    severity: str | None = Field(None, pattern="^(low|medium|high|critical)$", description="严重程度")
    message_id: int | None = Field(None, description="关联的 AI 消息 ID（可选）")
    agent_id: int | None = Field(None, description="关联的 Agent ID（可选）")
    screenshot_url: str | None = Field(None, max_length=500, description="截图 URL")
    tags: list[str] | None = None


class FeedbackUpdate(BaseModel):
    """处理反馈请求（管理端）"""

    status: str | None = Field(None, pattern="^(pending|resolved|ignored)$", description="处理状态")
    reply: str | None = Field(None, max_length=2000, description="管理员回复")


class FeedbackInfo(BaseModel):
    """反馈详情响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    content: str
    severity: str | None
    message_id: int | None
    conversation_id: int | None
    agent_id: int | None
    user_id: int
    rating: int | None
    tags: list[str] | None
    screenshot_url: str | None
    status: str
    reply: str | None
    replied_by: int | None
    replied_at: datetime | None
    created_at: datetime
    # 关联冗余字段
    username: str | None = None
    agent_name: str | None = None


class FeedbackStats(BaseModel):
    """反馈统计响应"""

    total: int
    bug_count: int
    feature_count: int
    usage_count: int
    other_count: int
    pending_count: int
    resolved_count: int
    daily: list[dict]
    category_distribution: list[dict]
