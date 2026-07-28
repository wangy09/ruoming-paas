"""
若茗 PaaS - 结构化日志配置（structlog + loguru）
Author: ruoming
"""
import logging
import sys
from pathlib import Path

import structlog
from loguru import logger as loguru_logger

from app.config import settings


def setup_logging() -> None:
    """初始化日志系统"""
    log_level = settings.LOG_LEVEL.upper()

    # ── 配置 structlog ────────────────────────────────────────────────
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_JSON:
        # 生产环境：JSON 格式
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # 开发环境：彩色可读格式
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── 配置 loguru（文件 sink）──────────────────────────────────────
    loguru_logger.remove()
    loguru_logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        if not settings.LOG_JSON
        else "{message}",
        serialize=settings.LOG_JSON,
    )

    # 文件输出（始终开启，开发环境同样写文件以支持溯源）
    # 优先使用 /app/logs（容器内绝对路径），回退到脚本相对路径
    log_dir = Path("/app/logs") if Path("/app").exists() else Path("logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)

    try:
        loguru_logger.add(
            log_dir / "ruoming_{time:YYYY-MM-DD}.log",
            rotation="00:00",        # 每天午夜轮转
            retention="30 days",     # 保留 30 天
            compression="gz",        # gzip 压缩历史日志
            level=log_level,
            serialize=True,          # 始终 JSON 格式，便于 grep/jq 分析
            enqueue=True,            # 异步写入，不阻塞主线程
        )

        # 错误单独写一份文件，方便快速定位
        loguru_logger.add(
            log_dir / "ruoming_error_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            compression="gz",
            level="ERROR",
            serialize=True,
            enqueue=True,
        )
    except PermissionError:
        pass  # 日志目录无权限，跳过文件日志

    # 捕获 uvicorn / sqlalchemy 等标准库日志到 structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )
