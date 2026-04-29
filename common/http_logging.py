"""HTTP request helpers with structured logging."""

from __future__ import annotations

import time
from typing import Any

import requests

from common.log_context import log_with_context


def http_request(
    logger,
    session,
    method: str,
    url: str,
    *,
    action: str | None = None,
    chat_id: str | None = None,
    retry_count: int | None = None,
    error_stage: str | None = None,
    **kwargs: Any,
):
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
            http_url=url,
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
            http_url=url,
            http_elapsed_ms=elapsed_ms,
            retry_count=retry_count,
            error_stage=error_stage,
        )
        raise exc
