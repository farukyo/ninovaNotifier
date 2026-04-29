"""Shared logging context helpers."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

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
    logger,
    level: str,
    message: str,
    *,
    exc_info: bool | BaseException | None = None,
    **fields: Any,
) -> None:
    """Log a message with merged context and extra fields."""
    extra = dict(get_log_context())
    extra.update({key: value for key, value in fields.items() if value is not None})
    log_method = getattr(logger, level, logger.info)
    log_method(message, extra=extra, exc_info=exc_info)
