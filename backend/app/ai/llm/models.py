"""
若茗 PaaS - AI 模型配置 ORM 模型
Author: ruoming
"""
from sqlalchemy import BigInteger, Boolean, Float, Integer, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class AiModelConfig(BaseModel):
    """
    AI 模型配置表（ai_model_config）。
    存储各厂商的 API Key（AES-256 加密）、模型 ID、参数上限等。
    api_key 字段使用 AES-256（Fernet）加密后存储，读取时需调用 decrypt_value() 解密。
    """

    __tablename__ = "ai_model_config"

    name: Mapped[str] = mapped_column(
        comment="配置名称（展示用）", nullable=False
    )
    provider: Mapped[str] = mapped_column(
        comment="提供商标识：zhuilu / openai / ollama", nullable=False
    )
    model_id: Mapped[str] = mapped_column(
        comment="模型 ID（调用时传给 API）", nullable=False
    )
    api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="API Key（AES-256 加密存储）"
    )
    base_url: Mapped[str | None] = mapped_column(
        nullable=True, comment="API 基础 URL"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否为默认对话模型"
    )
    is_embed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否为向量化专用模型"
    )
    is_rerank: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否为 Rerank 模型"
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, default=4096, server_default="4096", comment="最大 Token 数"
    )
    context_length: Mapped[int] = mapped_column(
        Integer, default=8192, server_default="8192", comment="上下文窗口长度"
    )
    remark: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1=启用，0=禁用"
    )
    # tenant_id=NULL 表示平台级公共模型，各租户可见；非 NULL 则仅该租户私有
