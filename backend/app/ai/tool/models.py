"""
若茗 PaaS - 工具链 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiTool(Base):
    """
    AI 工具定义表（ai_tool）。
    工具分为内置（builtin）、自定义（custom）、API 调用（api）三种类型。
    config 字段中的 API Key 等敏感信息使用 AES-256 加密存储。
    """

    __tablename__ = "ai_tool"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False, comment="工具名称")
    code: Mapped[str] = mapped_column(
        nullable=False, unique=True, comment="工具唯一标识码（如 builtin:web_search）"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="工具描述")
    tool_type: Mapped[str] = mapped_column(
        default="builtin", comment="工具类型：builtin / custom / api"
    )
    schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="工具参数 JSON Schema")
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", comment="工具配置（API Key 等，敏感值已加密）"
    )
    is_sandbox: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否在沙箱中执行（危险工具）"
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
