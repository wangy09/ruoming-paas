"""
若茗 PaaS - 用户 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysUser(BaseModel):
    """用户表"""

    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="登录用户名"
    )
    password: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="bcrypt 哈希密码"
    )
    nickname: Mapped[str | None] = mapped_column(String(64), comment="昵称/显示名")
    email: Mapped[str | None] = mapped_column(String(128), unique=True, comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    avatar: Mapped[str | None] = mapped_column(String(1024), comment="头像 URL")

    # 状态
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1正常 0禁用"
    )
    is_superplatform: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否平台超级管理员"
    )

    # 多租户字段
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属租户 ID")

    # 所属部门（组织）
    dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属部门 ID")

    # 登录安全
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="最后登录时间"
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(64), comment="最后登录 IP")
    login_fail_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="连续登录失败次数"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="账号锁定到期时间（NULL=未锁定）"
    )

    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class SysApiKey(BaseModel):
    """API Key 表（三方系统调用）"""

    __tablename__ = "sys_api_key"

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="API Key 名称")
    key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="SHA-256 哈希（查找用）"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="Key 前缀（展示用，如 rm_xxxxx）"
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="所属用户 ID")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1启用 0撤销"
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="过期时间（NULL=永不过期）"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="最后使用时间"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="用途描述")
