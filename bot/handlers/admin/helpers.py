"""
Admin yardımcı fonksiyonları.
"""

import os
from datetime import datetime
from bot.instance import START_TIME

# Admin ID - ENV'den alınır
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")

# Admin state'leri (duyuru/msg için)
admin_states = {}


def is_admin(message_or_call):
    """
    Mesaj veya callback'in admin'den gelip gelmediğini kontrol eder.

    :param message_or_call: telebot.types.Message veya CallbackQuery nesnesi
    :return: Admin ise True, değilse False
    """
    if hasattr(message_or_call, "chat"):
        return str(message_or_call.chat.id) == ADMIN_ID
    elif hasattr(message_or_call, "message"):
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
