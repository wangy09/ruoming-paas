"""第三方集成后台任务。"""
import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, cast

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.database import AsyncSessionFactory
from app.modules.integration.contact_sync import ContactSyncService
from app.modules.integration.models import SysIntegrationConnection
from app.modules.integration.schemas import ContactSyncRequest, ContactSyncStrategy
from app.modules.monitor.models import SysTaskExecutionLog
from app.modules.user.models import SysUser


@celery_app.task(name="app.modules.integration.tasks.sync_contact_connection")
def sync_contact_connection(
    connection_id: int,
    operator_id: int | None = None,
    _execution_log_id: int | None = None,
) -> dict:
    """按集成连接默认策略同步外部通讯录。"""
    return asyncio.run(_sync_contact_connection(connection_id, operator_id, _execution_log_id))


async def _sync_contact_connection(
    connection_id: int,
    operator_id: int | None,
    execution_log_id: int | None,
) -> dict:
    started = perf_counter()
    async with AsyncSessionFactory() as db:
        try:
            conn = await db.scalar(
                select(SysIntegrationConnection).where(
                    SysIntegrationConnection.id == connection_id,
                    SysIntegrationConnection.is_deleted == False,  # noqa: E712
                    SysIntegrationConnection.enabled == True,  # noqa: E712
                    SysIntegrationConnection.status == 1,
                )
            )
            if not conn:
                raise ValueError("集成连接不存在或未启用")
            if "contact_sync" not in (conn.capabilities or []):
                raise ValueError("当前连接未启用通讯录同步能力")
            if conn.provider not in ("feishu", "dingtalk", "wecom"):
                raise ValueError("当前平台不支持通讯录同步任务")

            operator = await _resolve_operator(db, conn, operator_id)
            strategy = _load_contact_sync_strategy(conn.config)
            request = ContactSyncRequest(
                provider=cast(Literal["feishu", "dingtalk", "wecom"], conn.provider),
                connection_id=conn.id,
                **strategy.model_dump(),
            )

            service = ContactSyncService(db, operator)
            result = await service.sync(request)
            payload = {
                "status": "partial" if result.errors else "success",
                "message": "通讯录同步完成" if not result.errors else "通讯录同步完成，但存在部分错误",
                "result": result.model_dump(),
            }
            await _update_execution_log(db, execution_log_id, "success", payload, None, started)
            await db.commit()
            return payload
        except Exception as exc:
            await db.rollback()
            await _update_execution_log(db, execution_log_id, "failed", None, str(exc), started)
            await db.commit()
            raise


async def _resolve_operator(
    db,
    conn: SysIntegrationConnection,
    operator_id: int | None,
) -> SysUser:
    candidate_ids = [item for item in (operator_id, conn.updated_by, conn.created_by) if item]
    if candidate_ids:
        candidate_conditions: list[Any] = [
            SysUser.id.in_(candidate_ids),
            SysUser.is_deleted == False,  # noqa: E712
            SysUser.status == 1,
        ]
        if conn.tenant_id is None:
            candidate_conditions.append(SysUser.is_superplatform == True)  # noqa: E712
            candidate_conditions.append(SysUser.tenant_id.is_(None))
        else:
            candidate_conditions.append(SysUser.tenant_id == conn.tenant_id)
        user = await db.scalar(
            select(SysUser)
            .where(*candidate_conditions)
            .limit(1)
        )
        if user:
            return user

    conditions: list[Any] = [
        SysUser.is_deleted == False,  # noqa: E712
        SysUser.status == 1,
    ]
    if conn.tenant_id is None:
        conditions.append(SysUser.is_superplatform == True)  # noqa: E712
        conditions.append(SysUser.tenant_id.is_(None))
    else:
        conditions.append(SysUser.tenant_id == conn.tenant_id)

    user = await db.scalar(select(SysUser).where(*conditions).order_by(SysUser.id).limit(1))
    if not user:
        raise ValueError("未找到可用于执行通讯录同步的操作人")
    return user


def _load_contact_sync_strategy(config: dict | None) -> ContactSyncStrategy:
    if not isinstance(config, dict):
        return ContactSyncStrategy()
    strategy = config.get("contact_sync_strategy")
    if not isinstance(strategy, dict):
        return ContactSyncStrategy()
    try:
        return ContactSyncStrategy.model_validate(strategy)
    except Exception:
        return ContactSyncStrategy()


async def _update_execution_log(
    db,
    execution_log_id: int | None,
    status: str,
    result: dict | None,
    error_msg: str | None,
    started: float,
) -> None:
    if not execution_log_id:
        return
    log = await db.get(SysTaskExecutionLog, execution_log_id)
    if not log:
        return
    finished_at = datetime.now(tz=timezone.utc)
    log.status = status
    log.finished_at = finished_at
    log.duration_ms = int((perf_counter() - started) * 1000)
    log.result = result
    log.error_msg = error_msg

