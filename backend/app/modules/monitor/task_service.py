"""
若茗 PaaS - 计划任务服务
负责任务的 CRUD、调度器集成（Celery Beat）、执行日志记录
Author: ruoming
"""
import importlib
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.utils.pagination import PageParams
from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog

logger = structlog.get_logger(__name__)


class TaskService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ──────────────────────────────────────────────
    # 任务 CRUD
    # ──────────────────────────────────────────────

    async def list_tasks(
        self,
        page_params: PageParams,
        name: str | None = None,
        func_name: str | None = None,
        status: int | None = None,
    ) -> dict:
        stmt = select(SysScheduledTask).where(SysScheduledTask.is_deleted == False).order_by(
            desc(SysScheduledTask.created_at)
        )
        if name:
            stmt = stmt.where(SysScheduledTask.name.ilike(f"%{name}%"))
        if func_name:
            stmt = stmt.where(SysScheduledTask.func_name == func_name)
        if status is not None:
            stmt = stmt.where(SysScheduledTask.status == status)

        total = await self.db.scalar(
            select(func.count(SysScheduledTask.id)).where(
                SysScheduledTask.is_deleted == False,
                *([SysScheduledTask.name.ilike(f"%{name}%")] if name else []),
                *([SysScheduledTask.func_name == func_name] if func_name else []),
                *([SysScheduledTask.status == status] if status is not None else []),
            )
        )
        rows = await self.db.execute(
            stmt.offset((page_params.page - 1) * page_params.page_size).limit(page_params.page_size)
        )
        items = [_task_to_dict(t) for t in rows.scalars().all()]
        return {"items": items, "total": total or 0, "page": page_params.page, "page_size": page_params.page_size}

    async def get_task(self, task_id: int) -> SysScheduledTask | None:
        result = await self.db.execute(
            select(SysScheduledTask).where(
                SysScheduledTask.id == task_id,
                SysScheduledTask.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def create_task(self, data: dict) -> SysScheduledTask:
        task = SysScheduledTask(**data)
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def update_task(self, task_id: int, data: dict) -> SysScheduledTask | None:
        task = await self.get_task(task_id)
        if not task:
            return None
        for k, v in data.items():
            setattr(task, k, v)
        await self.db.flush()
        return task

    async def delete_task(self, task_id: int) -> bool:
        task = await self.get_task(task_id)
        if not task:
            return False
        task.is_deleted = True
        return True

    async def set_status(self, task_id: int, status: int) -> bool:
        task = await self.get_task(task_id)
        if not task:
            return False
        task.status = status
        return True

    # ──────────────────────────────────────────────
    # 手动执行
    # ──────────────────────────────────────────────

    async def run_now(self, task_id: int) -> dict:
        """立即触发一次任务执行，返回 celery task_id"""
        task = await self.get_task(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        # 写一条 pending 日志
        log = SysTaskExecutionLog(
            task_id=task.id,
            task_name=task.name,
            status="pending",
            triggered_by="manual",
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        # 异步发送给 Celery
        try:
            args = task.args if isinstance(task.args, list) else []
            kwargs = task.kwargs if isinstance(task.kwargs, dict) else {}
            celery_result = celery_app.send_task(
                task.func_name,
                args=args,
                kwargs={**kwargs, "_execution_log_id": log.id},
            )
            log.celery_task_id = celery_result.id
            log.status = "running"
            log.started_at = datetime.now(tz=timezone.utc)

            # 更新任务上次运行时间
            task.last_run_at = log.started_at
        except Exception as e:
            log.status = "failed"
            log.error_msg = str(e)
            log.finished_at = datetime.now(tz=timezone.utc)
            logger.error("task_run_failed", task_id=task_id, error=str(e))

        return {"log_id": log.id, "celery_task_id": log.celery_task_id}

    # ──────────────────────────────────────────────
    # 执行日志
    # ──────────────────────────────────────────────

    async def list_logs(
        self,
        task_id: int | None,
        page_params: PageParams,
        status: str | None = None,
    ) -> dict:
        conditions = [SysTaskExecutionLog.is_deleted == False]
        if task_id is not None:
            conditions.append(SysTaskExecutionLog.task_id == task_id)
        if status:
            conditions.append(SysTaskExecutionLog.status == status)

        total = await self.db.scalar(select(func.count(SysTaskExecutionLog.id)).where(*conditions))
        rows = await self.db.execute(
            select(SysTaskExecutionLog)
            .where(*conditions)
            .order_by(desc(SysTaskExecutionLog.created_at))
            .offset((page_params.page - 1) * page_params.page_size)
            .limit(page_params.page_size)
        )
        items = [_log_to_dict(lg) for lg in rows.scalars().all()]
        return {"items": items, "total": total or 0, "page": page_params.page, "page_size": page_params.page_size}

    async def clear_logs(self, task_id: int | None = None, before_date: str | None = None) -> int:
        """软删除日志，返回删除条数"""
        conditions = [SysTaskExecutionLog.is_deleted == False]
        if task_id:
            conditions.append(SysTaskExecutionLog.task_id == task_id)
        if before_date:
            conditions.append(SysTaskExecutionLog.created_at <= before_date)

        rows = await self.db.execute(select(SysTaskExecutionLog).where(*conditions))
        logs = rows.scalars().all()
        for lg in logs:
            lg.is_deleted = True
        return len(logs)

    # ──────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────

    @staticmethod
    def get_available_functions() -> list[dict]:
        """
        自动扫描 Celery 已注册的 Task，返回下拉列表数据。
        仅返回 include 列表中模块内的 task（排除 celery 内置任务）。
        """
        for module_name in celery_app.conf.include or []:
            importlib.import_module(module_name)

        tasks = []
        for name, task in celery_app.tasks.items():
            # 过滤 celery 内置任务
            if name.startswith("celery."):
                continue
            # 尝试从 task 文档注释提取标签
            label = _task_label(name, task)
            tasks.append({"value": name, "label": label})
        return sorted(tasks, key=lambda x: x["value"])


def _task_label(name: str, task: Any) -> str:
    """从 task.__doc__ 或模块路径提取可读名称"""
    if task.__doc__:
        first_line = task.__doc__.strip().splitlines()[0]
        if first_line:
            return first_line[:60]
    # 用最后一段路径作为标签
    return name.split(".")[-1].replace("_task", "").replace("_", " ").title()


def _task_to_dict(t: SysScheduledTask) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "task_type": t.task_type,
        "func_name": t.func_name,
        "cron_expr": t.cron_expr,
        "interval_seconds": t.interval_seconds,
        "is_once": t.is_once,
        "args": t.args,
        "kwargs": t.kwargs,
        "status": t.status,
        "remark": t.remark,
        "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
        "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _log_to_dict(lg: SysTaskExecutionLog) -> dict:
    return {
        "id": lg.id,
        "task_id": lg.task_id,
        "task_name": lg.task_name,
        "celery_task_id": lg.celery_task_id,
        "status": lg.status,
        "started_at": lg.started_at.isoformat() if lg.started_at else None,
        "finished_at": lg.finished_at.isoformat() if lg.finished_at else None,
        "duration_ms": lg.duration_ms,
        "result": lg.result,
        "error_msg": lg.error_msg,
        "triggered_by": lg.triggered_by,
        "created_at": lg.created_at.isoformat() if lg.created_at else None,
    }
