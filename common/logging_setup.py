"""
Logging altyapısı: DailyFileHandler ve JSON formatter.

main.py'de çağrılır; diğer modüller sadece logging.getLogger("ninova") kullanır.
"""

import json
import logging
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from common.log_context import get_log_context

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

    main.py'de bir kez çağrılmalı. Dönen handler üzerinden current_log_path
    alınabilir (admin show_logs için).
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
