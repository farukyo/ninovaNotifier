# Bot modülü
from bot.instance import bot_instance as bot, set_check_callback, update_last_check_time

# Handler'ları import et (register için gerekli)
from bot.handlers.user import callbacks, commands  # noqa: F401
from bot.handlers.admin import (
    course_management,
    services,
    commands as admin_commands,
    callbacks as admin_callbacks,
)  # noqa: F401

__all__ = [
    "bot",
    "set_check_callback",
    "update_last_check_time",
    "admin_commands",
    "admin_callbacks",
    "course_management",
    "services",
]
