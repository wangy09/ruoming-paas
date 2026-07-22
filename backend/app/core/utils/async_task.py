import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_pending_tasks: set[asyncio.Task] = set()


def fire_and_forget(
    coro: Awaitable[Any],
    *,
    name: str = "unnamed_task",
    timeout: float = 30.0
) -> None:
    """
    安全的 fire-and-forget 异步任务执行器

    Args:
        coro: 异步协程对象
        name: 任务名称，用于日志和调试
        timeout: 超时时间（秒），默认为 30 秒

    Returns:
        None

    特性：
    - 自动跟踪任务，防止被垃圾回收
    - 捕获并记录所有异常，不会静默吞没
    - 支持超时控制，防止任务无限阻塞
    - 任务完成后自动从跟踪集合中移除
    """

    async def wrapped() -> None:
        try:
            async with asyncio.timeout(timeout):
                await coro
        except asyncio.TimeoutError:
            logger.error(
                "task_timeout",
                extra={
                    "task_name": name,
                    "timeout_seconds": timeout,
                },
            )
        except Exception as e:
            logger.error(
                "task_failed",
                extra={
                    "task_name": name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        finally:
            _pending_tasks.discard(task)

    task = asyncio.create_task(wrapped(), name=name)
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


def get_pending_tasks_count() -> int:
    """
    获取当前待处理的异步任务数量

    Returns:
        当前待处理任务数
    """
    return len(_pending_tasks)