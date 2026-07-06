"""计划任务调度器进程。"""
import asyncio
import os
import signal
from datetime import datetime, timedelta, timezone
from typing import Iterable

import structlog
from sqlalchemy import or_, select

from app.core.celery_app import celery_app
from app.database import AsyncSessionFactory, close_db
from app.modules.monitor.models import SysScheduledTask, SysTaskExecutionLog

logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = max(1, int(os.getenv("TASK_SCHEDULER_POLL_INTERVAL", "10")))
MAX_DUE_TASKS_PER_TICK = max(1, int(os.getenv("TASK_SCHEDULER_BATCH_SIZE", "20")))


class CronExpressionError(ValueError):
    """Cron 表达式解析错误。"""


async def run_scheduler() -> None:
    """启动计划任务调度器。"""
    stop_event = asyncio.Event()

    def _handle_stop() -> None:
        logger.info("task_scheduler_stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)

    logger.info(
        "task_scheduler_started",
        poll_interval=POLL_INTERVAL_SECONDS,
        batch_size=MAX_DUE_TASKS_PER_TICK,
    )

    try:
        while not stop_event.is_set():
            await dispatch_due_tasks()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
            except TimeoutError:
                pass
    finally:
        await close_db()
        logger.info("task_scheduler_stopped")


async def dispatch_due_tasks() -> int:
    """扫描并派发到期任务，返回本轮派发数量。"""
    now = datetime.now(tz=timezone.utc)
    dispatched = 0

    async with AsyncSessionFactory() as db:
        rows = await db.execute(
            select(SysScheduledTask)
            .where(
                SysScheduledTask.is_deleted == False,  # noqa: E712
                SysScheduledTask.status == 1,
                or_(SysScheduledTask.next_run_at.is_(None), SysScheduledTask.next_run_at <= now),
            )
            .order_by(SysScheduledTask.next_run_at.asc().nullsfirst(), SysScheduledTask.id.asc())
            .limit(MAX_DUE_TASKS_PER_TICK)
            .with_for_update(skip_locked=True)
        )
        tasks = rows.scalars().all()

        for task in tasks:
            try:
                if await _dispatch_task(db, task, now):
                    dispatched += 1
            except Exception as exc:
                logger.exception("task_scheduler_dispatch_failed", task_id=task.id, error=str(exc))
                task.next_run_at = _next_retry_time(now)

        await db.commit()

    if dispatched:
        logger.info("task_scheduler_dispatched", count=dispatched)
    return dispatched


async def _dispatch_task(db, task: SysScheduledTask, now: datetime) -> bool:
    if task.next_run_at is None:
        next_run_at = calculate_next_run_at(task, now)
        task.next_run_at = next_run_at
        logger.info(
            "scheduled_task_next_run_initialized",
            task_id=task.id,
            task_name=task.name,
            next_run_at=next_run_at.isoformat(),
        )
        return False

    args = task.args if isinstance(task.args, list) else []
    kwargs = task.kwargs if isinstance(task.kwargs, dict) else {}

    log = SysTaskExecutionLog(
        task_id=task.id,
        task_name=task.name,
        status="pending",
        triggered_by="scheduler",
        started_at=now,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    try:
        celery_result = celery_app.send_task(
            task.func_name,
            args=args,
            kwargs={**kwargs, "_execution_log_id": log.id},
        )
        log.celery_task_id = celery_result.id
        log.status = "running"
        task.last_run_at = now
        task.next_run_at = None if task.is_once else calculate_next_run_at(task, now)
        if task.is_once:
            task.status = 0
        logger.info(
            "scheduled_task_dispatched",
            task_id=task.id,
            task_name=task.name,
            celery_task_id=celery_result.id,
            next_run_at=task.next_run_at.isoformat() if task.next_run_at else None,
        )
        return True
    except Exception as exc:
        log.status = "failed"
        log.error_msg = str(exc)
        log.finished_at = datetime.now(tz=timezone.utc)
        task.next_run_at = _next_retry_time(now)
        raise


def calculate_next_run_at(task: SysScheduledTask, base: datetime | None = None) -> datetime:
    """根据任务配置计算下一次执行时间。"""
    current = base or datetime.now(tz=timezone.utc)
    if task.task_type == "interval":
        seconds = task.interval_seconds or 0
        if seconds < 10:
            raise ValueError("间隔任务 interval_seconds 不能小于 10 秒")
        return current + timedelta(seconds=seconds)
    if task.task_type == "cron":
        if not task.cron_expr:
            raise ValueError("Cron 任务缺少 cron_expr")
        return next_cron_time(task.cron_expr, current)
    raise ValueError(f"不支持的任务类型: {task.task_type}")


def next_cron_time(expr: str, base: datetime | None = None) -> datetime:
    """计算下一次 cron 执行时间，支持 5 段表达式。"""
    parts = expr.split()
    if len(parts) != 5:
        raise CronExpressionError("Cron 表达式必须包含 5 段：分 时 日 月 周")

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    days = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    weekdays = _parse_cron_field(parts[4], 0, 7)
    weekdays = {0 if item == 7 else item for item in weekdays}

    current = base or datetime.now(tz=timezone.utc)
    candidate = (current + timedelta(minutes=1)).replace(second=0, microsecond=0)
    max_candidate = candidate + timedelta(days=366)

    while candidate <= max_candidate:
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and cron_weekday in weekdays
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise CronExpressionError("一年内没有匹配的下一次执行时间，请检查 Cron 表达式")


def _parse_cron_field(raw: str, min_value: int, max_value: int) -> set[int]:
    values: set[int] = set()
    for part in raw.split(","):
        values.update(_parse_cron_part(part.strip(), min_value, max_value))
    if not values:
        raise CronExpressionError(f"Cron 字段为空: {raw}")
    return values


def _parse_cron_part(raw: str, min_value: int, max_value: int) -> Iterable[int]:
    if not raw:
        raise CronExpressionError("Cron 字段包含空片段")

    step = 1
    base = raw
    if "/" in raw:
        base, step_raw = raw.split("/", 1)
        step = int(step_raw)
        if step <= 0:
            raise CronExpressionError("Cron 步长必须大于 0")

    if base == "*":
        start, end = min_value, max_value
    elif "-" in base:
        start_raw, end_raw = base.split("-", 1)
        start, end = int(start_raw), int(end_raw)
    else:
        start = end = int(base)

    if start < min_value or end > max_value or start > end:
        raise CronExpressionError(f"Cron 字段超出范围: {raw}")
    return range(start, end + 1, step)


def _next_retry_time(now: datetime) -> datetime:
    return now + timedelta(minutes=1)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
