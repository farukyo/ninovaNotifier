"""Bounded background task runner for lightweight async work."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("ninova")

_MAX_WORKERS = 6
_MAX_PENDING = 64
_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="bot-bg")
_PENDING_SEM = threading.Semaphore(_MAX_PENDING)


def submit_background_task(task_name: str, func: Callable, *args, **kwargs) -> bool:
    """Submit a bounded background task.

    Returns False when pending queue is full to avoid unbounded memory growth.
    """
    if not _PENDING_SEM.acquire(blocking=False):
        logger.warning(f"[bg] Task queue full, skipping task: {task_name}")
        return False

    def _run():
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception(f"[bg] Task failed: {task_name}")
        finally:
            _PENDING_SEM.release()

    _EXECUTOR.submit(_run)
    return True
