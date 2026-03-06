# Bot modülü
from bot.handlers.admin import (
    callbacks as admin_callbacks,
)
from bot.handlers.admin import (
    commands as admin_commands,
)
from bot.handlers.admin import (
    course_management,
    services,
)

# Handler'ları import et (register için gerekli)
from bot.handlers.user import callbacks, commands  # noqa: F401
from bot.instance import bot_instance as bot
from bot.instance import set_check_callback, update_last_check_time

__all__ = [
    "admin_callbacks",
    "admin_commands",
    "bot",
    "course_management",
    "services",
    "set_check_callback",
    "update_last_check_time",
]
