"""
若茗 PaaS - 第三方协作平台集成模型
"""
from sqlalchemy import BigInteger, Boolean, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysIntegrationConnection(BaseModel):
    """第三方平台连接配置。敏感凭证统一加密存储在 encrypted_config。"""

    __tablename__ = "sys_integration_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "name", name="uq_integration_tenant_provider_name"),
    )

    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="平台：feishu/dingtalk/wecom/custom"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="连接名称")
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True, comment="是否启用"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True, comment="是否默认连接"
    )
    capabilities: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", comment="已启用能力"
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="非敏感配置")
    encrypted_config: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密敏感配置 JSON")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", index=True, comment="状态：1正常 0停用"
    )
    last_test_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="最近连通性测试状态：success/failed"
    )
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近连通性测试说明")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人")
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="更新人")
