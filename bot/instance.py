import telebot
from datetime import datetime
from common.config import TELEGRAM_TOKEN

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
        except Exception:
            pass

    bot_instance.answer_callback_query = _safe_answer
