"""
若茗 PaaS - 消息中心 ORM 模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysNotice(BaseModel):
    """平台公告主表"""

    __tablename__ = "sys_notice"
    __table_args__ = {"comment": "平台公告表"}

    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="公告标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="公告内容")
    notice_type: Mapped[str] = mapped_column(
        String(32), default="notice", server_default="notice", comment="公告类型：notice=公告"
    )
    target_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="投放范围：all=全平台/dept=部门/user=指定用户"
    )
    target_dept_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True, comment="目标部门 ID 列表")
    target_user_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True, comment="目标用户 ID 列表")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="状态：0草稿 1已发布"
    )
    publisher_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="发布人 ID")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="发布时间"
    )
    receiver_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="接收人数"
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")


class SysUserMessage(BaseModel):
    """用户消息收件箱"""

    __tablename__ = "sys_user_message"
    __table_args__ = {"comment": "用户消息收件箱表"}

    notice_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="来源公告 ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="接收用户 ID")
    sender_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="发送人 ID")
    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="消息标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    message_type: Mapped[str] = mapped_column(
        String(32), default="notice", server_default="notice", comment="消息类型：notice=公告"
    )
    is_read: Mapped[bool] = mapped_column(default=False, server_default="false", comment="是否已读")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="阅读时间")
