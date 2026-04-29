"""User action audit logging helpers."""

import logging
import uuid

from common.log_context import log_with_context

logger = logging.getLogger("ninova")


def new_user_request_id(prefix: str = "usr") -> str:
    """Generate short request id for correlating user-side logs."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def log_user_action(
    actor_id: str,
    action: str,
    *,
    status: str = "ok",
    request_id: str | None = None,
    details: str | None = None,
    level: str = "info",
) -> None:
    """Emit consistent user audit logs."""
    parts = [f"[user] actor={actor_id}", f"action={action}", f"status={status}"]
    if request_id:
        parts.append(f"request_id={request_id}")
    if details:
        parts.append(f"details={details}")
    message = " | ".join(parts)
    log_with_context(
        logger,
        level,
        message,
        chat_id=str(actor_id),
        action=action,
        request_id=request_id,
    )
