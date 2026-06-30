"""
若茗 PaaS - 系统监控 ORM 模型
包含计划任务定义表 + 执行日志表
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysScheduledTask(BaseModel):
    """计划任务定义"""

    __tablename__ = "sys_scheduled_task"
    __table_args__ = {"comment": "计划任务定义表"}

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务名称")
    task_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="interval",
        comment="任务类型：cron=周期（cron表达式）/ interval=间隔"
    )
    func_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="Celery Task 完整路径，如 app.ai.knowledge.tasks.reindex_all_task"
    )
    # cron 类型专用
    cron_expr: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Cron 表达式，如 0 2 * * *（task_type=cron 时有效）"
    )
    # interval 类型专用
    interval_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="间隔秒数（task_type=interval 时有效）"
    )
    is_once: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否一次性任务（执行完自动停用）"
    )
    args: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="任务位置参数列表（JSON Array）")
    kwargs: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="任务关键字参数（JSON Object）")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1=启用 0=停用"
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="上次执行时间"
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="下次预计执行时间"
    )


class SysTaskExecutionLog(BaseModel):
    """计划任务执行日志"""

    __tablename__ = "sys_task_execution_log"
    __table_args__ = {"comment": "计划任务执行日志表"}

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="关联任务ID")
    task_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务名称（冗余）")
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="Celery Task ID")
    status: Mapped[str] = mapped_column(
        String(16), default="pending",
        comment="状态：pending=等待 / running=执行中 / success=成功 / failed=失败"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="结束时间"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="执行耗时（毫秒）")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="执行结果")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    triggered_by: Mapped[str] = mapped_column(
        String(32), default="scheduler", comment="触发方式：scheduler=调度 / manual=手动触发"
    )
