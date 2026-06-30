"""
若茗 PaaS - 消息中心 Pydantic 模型
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NoticeCreate(BaseModel):
    """创建平台公告"""

    title: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1)
    target_type: str = Field(..., description="all/dept/user")
    target_dept_ids: list[int] = Field(default_factory=list)
    target_user_ids: list[int] = Field(default_factory=list)
    remark: str | None = Field(None, max_length=255)
    publish_now: bool = Field(default=False, description="创建后立即发布")

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        if value not in {"all", "dept", "user"}:
            raise ValueError("target_type 只能是 all/dept/user")
        return value


class NoticeUpdate(BaseModel):
    """更新平台公告"""

    title: str | None = Field(None, min_length=1, max_length=128)
    content: str | None = Field(None, min_length=1)
    target_type: str | None = Field(None, description="all/dept/user")
    target_dept_ids: list[int] | None = None
    target_user_ids: list[int] | None = None
    remark: str | None = Field(None, max_length=255)

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str | None) -> str | None:
        if value is not None and value not in {"all", "dept", "user"}:
            raise ValueError("target_type 只能是 all/dept/user")
        return value


class NoticeInfo(BaseModel):
    """公告响应"""

    id: int
    title: str
    content: str
    notice_type: str
    target_type: str
    target_dept_ids: list[int] | None
    target_user_ids: list[int] | None
    status: int
    publisher_id: int | None
    published_at: datetime | None
    receiver_count: int
    remark: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageInfo(BaseModel):
    """用户消息响应"""

    id: int
    notice_id: int | None
    user_id: int
    sender_id: int | None
    title: str
    content: str
    message_type: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageUnreadSummary(BaseModel):
    """未读消息摘要"""

    unread_count: int
    latest: MessageInfo | None = None
