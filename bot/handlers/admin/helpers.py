"""
Admin yardımcı fonksiyonları.
"""

import logging
import os
import time
import uuid
from datetime import datetime

from bot.instance import START_TIME

# Admin ID - ENV'den alınır
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")

# Admin state'leri (duyuru/msg için)
ADMIN_STATE_TTL_SECONDS = 30 * 60
admin_states: dict[str, tuple[str, float]] = {}
logger = logging.getLogger("ninova")


def log_admin_action(
    actor_id: str,
    action: str,
    *,
    status: str = "ok",
    request_id: str | None = None,
    target_id: str | None = None,
    details: str | None = None,
    level: str = "info",
) -> None:
    """Emit consistent admin audit logs."""
    parts = [f"[admin] actor={actor_id}", f"action={action}", f"status={status}"]
    if target_id:
        parts.append(f"target={target_id}")
    if request_id:
        parts.append(f"request_id={request_id}")
    if details:
        parts.append(f"details={details}")
    message = " | ".join(parts)
    getattr(logger, level, logger.info)(message)


def new_admin_request_id(prefix: str = "adm") -> str:
    """Generate short request id for correlating admin logs."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def cleanup_admin_states(now: float | None = None) -> int:
    """Drop expired admin states and return removed count."""
    current_time = now or time.time()
    expired_keys = [
        key
        for key, (_state, ts) in admin_states.items()
        if current_time - ts > ADMIN_STATE_TTL_SECONDS
    ]
    for key in expired_keys:
        admin_states.pop(key, None)
    return len(expired_keys)


def set_admin_state(chat_id: str, state: str) -> None:
    cleanup_admin_states()
    admin_states[str(chat_id)] = (state, time.time())


def get_admin_state(chat_id: str) -> str | None:
    cleanup_admin_states()
    item = admin_states.get(str(chat_id))
    if not item:
        return None
    state, _ts = item
    return state


def pop_admin_state(chat_id: str) -> str | None:
    cleanup_admin_states()
    item = admin_states.pop(str(chat_id), None)
    if not item:
        return None
    state, _ts = item
    return state


def has_admin_state(chat_id: str) -> bool:
    cleanup_admin_states()
    return str(chat_id) in admin_states


def is_admin(message_or_call):
    """
    Mesaj veya callback'in admin'den gelip gelmediğini kontrol eder.

    :param message_or_call: telebot.types.Message veya CallbackQuery nesnesi
    :return: Admin ise True, değilse False
    """
    if hasattr(message_or_call, "chat"):
        return str(message_or_call.chat.id) == ADMIN_ID
    if hasattr(message_or_call, "message"):
        return str(message_or_call.message.chat.id) == ADMIN_ID
    return False


def get_uptime():
    """
    Bot çalışma süresini hesaplar ve okunabilir formata çevirir.

    :return: Uptime string'i ("2g 5s 30dk" formatında)
    """
    delta = datetime.now() - START_TIME
    days, remainder = divmod(int(delta.total_seconds()), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}g {hours}s {minutes}dk"
    return f"{hours}s {minutes}dk {seconds}sn"
