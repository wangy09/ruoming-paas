"""
若茗 PaaS - 配置中心 ORM 模型（四级分层：全局→租户→应用→用户）
Author: ruoming
"""
from sqlalchemy import BigInteger, Boolean, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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
    category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="配置分类：system/security/file/ai/message/login"
    )
    config_type: Mapped[str] = mapped_column(
        String(32),
        default="input",
        server_default="input",
        comment="表单控件类型：input/textarea/switch/select/json/password/number",
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="默认值")
    options: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True, comment="选项 JSON")
    required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否必填"
    )
    regex: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="正则校验")
    min_value: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最小值")
    max_value: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最大值")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", index=True, comment="状态：1启用 0停用"
    )

    # 元信息
    label: Mapped[str | None] = mapped_column(String(64), comment="展示名称")
    description: Mapped[str | None] = mapped_column(Text, comment="配置说明")
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否对前端可见（安全下发）"
    )


class SysConfigHistory(BaseModel):
    """
    配置变更历史表

    记录每次配置项变更的旧值、新值及操作人，用于审计和回滚。
    """

    __tablename__ = "sys_config_history"

    config_key: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True, comment="配置键"
    )
    scope_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="层级：global/tenant/app/user"
    )
    scope_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="层级 ID（tenant_id / user_id 等）"
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变更前的值")
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="变更后的值")
    changed_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="操作人用户 ID"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
