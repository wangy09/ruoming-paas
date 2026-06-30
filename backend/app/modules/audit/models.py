"""
若茗 PaaS - 审计日志 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysAuditLog(BaseModel):
    """操作审计日志（变更前后快照）"""

    __tablename__ = "sys_audit_log"

    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="操作用户 ID")
    username: Mapped[str | None] = mapped_column(String(64), comment="操作用户名（快照）")

    # 操作信息
    module: Mapped[str | None] = mapped_column(String(64), comment="模块名称")
    action: Mapped[str | None] = mapped_column(String(64), comment="操作动作（create/update/delete）")
    resource_type: Mapped[str | None] = mapped_column(String(64), comment="资源类型")
    resource_id: Mapped[str | None] = mapped_column(String(64), comment="资源 ID")
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="事件类型（枚举）"
    )

    # 变更快照（JSONB）
    before_data: Mapped[dict | None] = mapped_column(JSONB, comment="变更前数据快照")
    after_data: Mapped[dict | None] = mapped_column(JSONB, comment="变更后数据快照")
    detail: Mapped[dict | None] = mapped_column(JSONB, comment="附加详情")

    # 请求/响应数据
    request_body: Mapped[dict | None] = mapped_column(JSONB, comment="请求体数据（脱敏后）")
    response_body: Mapped[dict | None] = mapped_column(JSONB, comment="响应体数据")
    status_code: Mapped[int | None] = mapped_column(Integer, comment="HTTP 响应状态码")

    # 请求上下文
    request_ip: Mapped[str | None] = mapped_column(String(64), comment="请求 IP")
    user_agent: Mapped[str | None] = mapped_column(Text, comment="User-Agent")
    browser: Mapped[str | None] = mapped_column(String(64), comment="浏览器")
    os: Mapped[str | None] = mapped_column(String(64), comment="操作系统")
    device: Mapped[str | None] = mapped_column(String(64), comment="设备类型")
    trace_id: Mapped[str | None] = mapped_column(String(64), comment="请求 trace_id")
    path: Mapped[str | None] = mapped_column(String(256), comment="请求路径")
    method: Mapped[str | None] = mapped_column(String(10), comment="HTTP 方法")

    # 结果
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="操作结果：1成功 0失败"
    )
    error_msg: Mapped[str | None] = mapped_column(Text, comment="失败时的错误信息")


class SysLoginLog(BaseModel):
    """登录日志"""

    __tablename__ = "sys_login_log"

    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="用户 ID")
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="登录用户名")

    login_type: Mapped[str] = mapped_column(
        String(32), default="password", comment="登录方式：password/api_key/oauth"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="结果：1成功 0失败"
    )
    fail_reason: Mapped[str | None] = mapped_column(String(128), comment="失败原因")

    login_ip: Mapped[str | None] = mapped_column(String(64), comment="登录 IP")
    user_agent: Mapped[str | None] = mapped_column(Text, comment="User-Agent")
    device: Mapped[str | None] = mapped_column(String(64), comment="设备类型")
    browser: Mapped[str | None] = mapped_column(String(64), comment="浏览器")
    os: Mapped[str | None] = mapped_column(String(64), comment="操作系统")


class SysSecurityEvent(BaseModel):
    """安全事件日志（Token 重放、暴力破解等）"""

    __tablename__ = "sys_security_event"

    user_id: Mapped[int | None] = mapped_column(BigInteger)

    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件类型：brute_force/token_replay/cross_tenant"
    )
    severity: Mapped[str] = mapped_column(
        String(16), default="warning", comment="严重程度：info/warning/critical"
    )
    detail: Mapped[dict | None] = mapped_column(JSONB)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64))
