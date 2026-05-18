from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import telebot
from telebot import apihelper

if TYPE_CHECKING:
    from collections.abc import Callable

from core.config import TELEGRAM_TOKEN

logger = logging.getLogger("ninova")


class _BotExceptionHandler(telebot.ExceptionHandler):
    """Catch handler exceptions so transient network issues don't stop polling."""

    def handle(self, exception: Exception) -> bool:
        logger.warning(
            f"TeleBot handler exception captured: {type(exception).__name__}: {exception}"
        )
        logger.debug("TeleBot handler traceback")
        return True


# Telegram API retry settings for transient network errors.
apihelper.RETRY_ON_ERROR = True
apihelper.MAX_RETRIES = 3
apihelper.RETRY_TIMEOUT = 2
# Explicit request timeouts for Telegram API calls.
apihelper.connect_timeout = 10
apihelper.read_timeout = 30
# Keep upper-case aliases for compatibility with different pytelegrambotapi versions.
apihelper.CONNECT_TIMEOUT = 10
apihelper.READ_TIMEOUT = 30

bot_instance = (
    telebot.TeleBot(TELEGRAM_TOKEN, exception_handler=_BotExceptionHandler())
    if TELEGRAM_TOKEN
    else None
)
START_TIME = datetime.now()
LAST_CHECK_TIME = None
_check_callback = None


def set_check_callback(callback: Callable) -> None:
    """
    Otomatik kontrol (polling) fonksiyonunu ayarlar.

    :param callback: Çağrılacak kontrol fonksiyonu (callable)
    """
    global _check_callback
    _check_callback = callback


def get_check_callback() -> Callable | None:
    """
    Ayarlanmış olan kontrol fonksiyonunu döndürür.

    :return: Kayıtlı callback fonksiyonu veya None
    """
    return _check_callback


def update_last_check_time() -> None:
    """Son başarılı kontrol zamanını (LAST_CHECK_TIME) günceller."""
    global LAST_CHECK_TIME
    LAST_CHECK_TIME = datetime.now()


if bot_instance:
    # Callback hatalarını (timeout vb.) önlemek için sarmalayıcı
    _orig_answer = bot_instance.answer_callback_query

    def _safe_answer(*args, **kwargs):
        """Answer callback queries safely.

        TeleBot bazı durumlarda (timeout/ağ vb.) exception fırlatabiliyor; bu sarmalayıcı
        botun çökmesini engeller.
        """
        try:
            return _orig_answer(*args, **kwargs)
        except Exception as e:
            # Log the error with context
            callback_query_id = kwargs.get("callback_query_id") or (args[0] if args else "unknown")
            logger.exception(f"Failed to answer callback query {callback_query_id}: {e}")

    bot_instance.answer_callback_query = _safe_answer

    # Validate bot token at startup
    if not TELEGRAM_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN not set. Bot will not be able to function!")
    else:
        logger.info("✅ Telegram bot initialized successfully")
