"""
若茗 PaaS - Prompt 模板版本化 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.database import Base


class AiPromptTemplate(BaseModel):
    """
    Prompt 模板主表（ai_prompt_template）。
    每次修改内容时新增 AiPromptVersion 版本快照，原版本保留不修改。
    Agent 通过引用 prompt_template_id 实现 Prompt 与 Agent 配置解耦。
    """

    __tablename__ = "ai_prompt_template"

    name: Mapped[str] = mapped_column(nullable=False, comment="模板名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(
        nullable=True, comment="分类：system / user / few-shot / chain"
    )
    current_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="当前生效版本号"
    )
    variables: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]",
        comment="模板变量声明，如 ['user_name', 'context']"
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class AiPromptVersion(Base):
    """
    Prompt 版本快照表（ai_prompt_version）。
    每次修改模板内容时新增一行，旧版本永久保留，支持回滚和审计。
    """

    __tablename__ = "ai_prompt_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="所属模板 ID"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号（递增）")
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="模板内容（支持 {{variable}} 插值）"
    )
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True, comment="本次修改说明")
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="可选：评测得分")
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
        comment="是否已发布（只有已发布版本可被 Agent 引用）"
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
