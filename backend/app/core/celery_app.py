"""Celery 异步任务配置"""
import os

from celery import Celery

from app.config import settings

celery_app = Celery(
    "ruoming_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=None,
    include=["app.ai.knowledge.tasks", "app.modules.monitor.tasks"],
)

celery_app.conf.update(
    result_expires=3600,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_routes={
        "app.ai.knowledge.tasks.*": {"queue": "knowledge"},
        "rmtask_test": {"queue": "knowledge"},
    },
    task_annotations={
        "app.ai.knowledge.tasks.index_document": {"rate_limit": "10/m"},
    },
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=False,
    broker_connection_retry=True,
    broker_connection_max_retries=3,
)
