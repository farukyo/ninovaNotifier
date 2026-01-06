# Bot modülü
from bot.core import bot_instance as bot, set_check_callback, update_last_check_time

# Handler'ları import et (register için gerekli)
from bot.handlers import admin, callbacks, commands  # noqa: F401

__all__ = ["bot", "set_check_callback", "update_last_check_time"]
