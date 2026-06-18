"""
若茗 PaaS - 配置中心 ORM 模型（四级分层：全局→租户→应用→用户）
Author: ruoming
"""
from sqlalchemy import BigInteger, Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysConfig(BaseModel):
    """
    系统配置表（四级分层覆盖）

    优先级（由高到低）：user > app > tenant > global
    读取时从高优先级向下查找，找到即返回。
    """

    __tablename__ = "sys_config"
    __table_args__ = (
        UniqueConstraint(
            "scope", "tenant_id", "app_key", "user_id", "config_key",
            name="uq_config_scope_key",
        ),
    )

    # 层级定位
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="层级：global/tenant/app/user"
    )
    # tenant_id 继承自 BaseModel，scope=global 时为 NULL
    app_key: Mapped[str | None] = mapped_column(
        String(64), comment="模块标识（scope=app 时有效，如 'ai'/'export'）"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="用户 ID（scope=user 时有效）"
    )

    # 配置内容
    config_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="配置键，如 theme.primary_color"
    )
    config_val: Mapped[str | None] = mapped_column(Text, comment="配置值（复杂值用 JSON 字符串）")
    val_type: Mapped[str] = mapped_column(
        String(16),
        default="string",
        server_default="string",
        comment="值类型：string/int/bool/json",
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否加密存储"
    )

    # 元信息
    label: Mapped[str | None] = mapped_column(String(64), comment="展示名称")
    description: Mapped[str | None] = mapped_column(Text, comment="配置说明")
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否对前端可见（安全下发）"
    )
