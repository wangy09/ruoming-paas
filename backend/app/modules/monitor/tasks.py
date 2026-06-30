"""系统监控测试任务"""
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.celery_app import celery_app
from app.modules.monitor.models import SysTaskExecutionLog


_sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
_sync_engine = create_engine(_sync_db_url, pool_pre_ping=True)
_SyncSession = sessionmaker(bind=_sync_engine)


@celery_app.task(name="rmtask_test")
def rmtask_test(_execution_log_id: int | None = None) -> dict:
    """测试任务 rmtask_test"""
    started = perf_counter()
    result = {
        "status": "success",
        "message": "rmtask_test executed successfully",
        "executed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    if _execution_log_id:
        with _SyncSession() as session:
            try:
                log = session.get(SysTaskExecutionLog, _execution_log_id)
                if log:
                    finished_at = datetime.now(tz=timezone.utc)
                    log.status = "success"
                    log.finished_at = finished_at
                    log.duration_ms = int((perf_counter() - started) * 1000)
                    log.result = result
                    session.commit()
            except Exception:
                session.rollback()
                raise

    return result
