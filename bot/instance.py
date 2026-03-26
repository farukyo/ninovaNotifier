import logging
from datetime import datetime

import telebot

from common.config import TELEGRAM_TOKEN

logger = logging.getLogger("ninova")

bot_instance = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
START_TIME = datetime.now()
LAST_CHECK_TIME = None
_check_callback = None


def set_check_callback(callback):
    """
    Otomatik kontrol (polling) fonksiyonunu ayarlar.

    :param callback: Çağrılacak kontrol fonksiyonu (callable)
    """
    global _check_callback
    _check_callback = callback


def get_check_callback():
    """
    Ayarlanmış olan kontrol fonksiyonunu döndürür.

    :return: Kayıtlı callback fonksiyonu veya None
    """
    return _check_callback


def update_last_check_time():
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
