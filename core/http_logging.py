"""HTTP request helpers with structured logging.

migrated from: common/http_logging.py
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

import requests

from core.logger import log_with_context

if TYPE_CHECKING:
    import logging


def _redact_url(url: str) -> str:
    # fix: prevent bot token from appearing in log files (BUG-S1)
    return re.sub(r"(api\.telegram\.org/bot)[^/]+", r"\1[REDACTED]", url)


def http_request(
    logger: logging.Logger,
    session: Any,
    method: str,
    url: str,
    *,
    action: str | None = None,
    chat_id: str | None = None,
    retry_count: int | None = None,
    error_stage: str | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Execute an HTTP request and emit structured logs."""
    start = time.perf_counter()
    try:
        response = session.request(method, url, **kwargs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log_with_context(
            logger,
            "info",
            "HTTP request completed",
            chat_id=chat_id,
            action=action,
            http_method=method,
            http_url=_redact_url(url),
            http_status=response.status_code,
            http_elapsed_ms=elapsed_ms,
            retry_count=retry_count,
        )
        return response
    except requests.RequestException as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log_with_context(
            logger,
            "warning",
            "HTTP request failed",
            chat_id=chat_id,
            action=action,
            http_method=method,
            http_url=_redact_url(url),
            http_elapsed_ms=elapsed_ms,
            retry_count=retry_count,
            error_stage=error_stage,
        )
        raise exc
