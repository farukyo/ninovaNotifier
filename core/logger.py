"""Logging configuration: DailyFileHandler, JSON formatter, ContextVar filter.

migrated from:
  common/logging_setup.py  — DailyFileHandler, _JsonFormatter, setup_logging
  common/log_context.py    — ContextVar-based context helpers
"""

# migrated from: common/logging_setup.py, common/log_context.py
from __future__ import annotations

import json
import logging
import time
from contextlib import suppress
from contextvars import ContextVar
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# ---------------------------------------------------------------------------
# ContextVar helpers (migrated from: common/log_context.py)
# ---------------------------------------------------------------------------

_LOG_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, Any]:
    """Return the current logging context."""
    return _LOG_CONTEXT.get() or {}


def set_log_context(**fields: Any) -> None:
    """Set or update context fields for the current execution."""
    ctx = dict(get_log_context())
    ctx.update({key: value for key, value in fields.items() if value is not None})
    _LOG_CONTEXT.set(ctx)


def clear_log_context(*keys: str) -> None:
    """Clear specific context keys (or all if none provided)."""
    if not keys:
        _LOG_CONTEXT.set({})
        return
    ctx = dict(get_log_context())
    for key in keys:
        ctx.pop(key, None)
    _LOG_CONTEXT.set(ctx)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    *,
    exc_info: bool | BaseException | None = None,
    **fields: Any,
) -> None:
    """Log a message with merged context and extra fields."""
    extra = dict(get_log_context())
    extra.update({key: value for key, value in fields.items() if value is not None})
    log_method: Callable = getattr(logger, level, logger.info)
    log_method(message, extra=extra, exc_info=exc_info)


# ---------------------------------------------------------------------------
# Logging setup (migrated from: common/logging_setup.py)
# ---------------------------------------------------------------------------

_EXTRA_FIELDS = (
    "chat_id",
    "action",
    "request_id",
    "http_method",
    "http_url",
    "http_status",
    "http_elapsed_ms",
    "retry_count",
    "error_stage",
    "callback_data_len",
)


class _ContextFilter(logging.Filter):
    """Inject shared context fields into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        for key, value in context.items():
            if value is not None and not hasattr(record, key):
                setattr(record, key, value)
        return True


class _JsonFormatter(logging.Formatter):
    """Her log satırını tek satır JSON olarak formatlar."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "thread": record.threadName,
            "process": record.process,
        }
        for key in _EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class DailyFileHandler(logging.FileHandler):
    """Gün değişince app_YYYY-MM-DD.log adlı yeni dosyaya geçer."""

    def __init__(self, logs_dir: Path, encoding: str = "utf-8"):
        self.logs_dir = logs_dir
        self.current_date = datetime.now().date()
        filename = self.logs_dir / f"app_{self.current_date.strftime('%Y-%m-%d')}.log"
        super().__init__(filename, mode="a", encoding=encoding)

    def emit(self, record: logging.LogRecord) -> None:
        today = datetime.now().date()
        if today != self.current_date:
            self.current_date = today
            self.acquire()
            try:
                if self.stream:
                    self.stream.close()
                    self.stream = None
                self.baseFilename = str(
                    self.logs_dir / f"app_{self.current_date.strftime('%Y-%m-%d')}.log"
                )
                self.stream = self._open()
            finally:
                self.release()
        super().emit(record)

    @property
    def current_log_path(self) -> Path:
        """Şu an yazılan log dosyasının yolu."""
        return self.logs_dir / f"app_{self.current_date.strftime('%Y-%m-%d')}.log"


def cleanup_old_logs(logs_dir: Path, keep_days: int = 30) -> None:
    """keep_days günden eski app_*.log dosyalarını siler."""
    cutoff = time.time() - keep_days * 86400
    for log_path in logs_dir.glob("app_*.log"):
        if log_path.stat().st_mtime < cutoff:
            with suppress(OSError):
                log_path.unlink()


def setup_logging(logs_dir: Path) -> DailyFileHandler:
    """
    Logging'i yapılandırır; DailyFileHandler döndürür.

    main.py'de bir kez çağrılmalı.
    """
    cleanup_old_logs(logs_dir)
    handler = DailyFileHandler(logs_dir, encoding="utf-8")
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_ContextFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, DailyFileHandler) for h in root.handlers):
        root.addHandler(handler)
    root.addFilter(_ContextFilter())
    return handler
