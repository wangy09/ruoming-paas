"""
若茗 PaaS - 租户 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysTenant(BaseModel):
    """租户表"""

    __tablename__ = "sys_tenant"

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="租户名称")
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="租户唯一标识（域名前缀）"
    )
    domain: Mapped[str | None] = mapped_column(String(128), comment="自定义域名")
    logo: Mapped[str | None] = mapped_column(String(256), comment="租户 Logo URL")
    plan: Mapped[str] = mapped_column(
        String(32), default="basic", server_default="basic", comment="套餐：trial/basic/pro/enterprise"
    )

    # 配额限制
    max_users: Mapped[int] = mapped_column(Integer, default=10, server_default="10", comment="最大用户数")
    max_storage_gb: Mapped[float] = mapped_column(
        Numeric(10, 2), default=5.0, server_default="5.0", comment="存储配额(GB)"
    )
    max_api_calls_day: Mapped[int] = mapped_column(
        Integer, default=1000, server_default="1000", comment="每日 API 调用次数上限"
    )
    max_ai_tokens_day: Mapped[int] = mapped_column(
        Integer, default=100000, server_default="100000", comment="每日 AI Token 消耗上限"
    )
    max_concurrent: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", comment="最大并发 AI 请求数"
    )

    # 时间状态
    expire_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="过期时间（NULL=永久）"
    )
    trial_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="试用期结束时间"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        server_default="1",
        comment="状态：1正常 2试用 3过期 0禁用",
    )

    # 个性化配置（JSONB）
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", comment="个性化配置（主题色、功能开关等）"
    )

    # 联系信息
    contact_email: Mapped[str | None] = mapped_column(String(128), comment="联系邮箱")
    contact_phone: Mapped[str | None] = mapped_column(String(20), comment="联系电话")

    # 审核信息
    registered_by: Mapped[int | None] = mapped_column(BigInteger, comment="注册人用户ID")
    approved_by: Mapped[int | None] = mapped_column(BigInteger, comment="审核人（平台超管）")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="审核时间")

    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class SysTenantUsage(BaseModel):
    """租户每日用量统计表"""

    __tablename__ = "sys_tenant_usage"

    # 覆盖父类 tenant_id（不能为 NULL）
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="租户ID"
    )
    stat_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="统计日期 YYYY-MM-DD")
    api_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="API 调用次数")
    ai_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="AI Token 消耗")
    storage_bytes: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="存储占用字节"
    )
