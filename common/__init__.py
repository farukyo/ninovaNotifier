"""
Core modülü - Sistem yapılandırması ve yardımcı fonksiyonlar.
"""

from common.config import (
    CHECK_INTERVAL,
    DATA_FILE,
    ENCRYPTION_KEY,
    HEADERS,
    TELEGRAM_TOKEN,
    USER_SESSIONS,
    USERS_FILE,
    cipher_suite,
    console,
    load_all_users,
    save_all_users,
)
from common.utils import (
    decrypt_password,
    encrypt_password,
    escape_html,
    get_file_icon,
    load_saved_grades,
    parse_turkish_date,
    save_grades,
    send_telegram_document,
    send_telegram_message,
    update_user_data,
)

__all__ = [
    "CHECK_INTERVAL",
    "DATA_FILE",
    "ENCRYPTION_KEY",
    "HEADERS",
    "TELEGRAM_TOKEN",
    "USERS_FILE",
    "USER_SESSIONS",
    "cipher_suite",
    # Config
    "console",
    "decrypt_password",
    "encrypt_password",
    "escape_html",
    "get_file_icon",
    "load_all_users",
    "load_saved_grades",
    # Utils
    "parse_turkish_date",
    "save_all_users",
    "save_grades",
    "send_telegram_document",
    "send_telegram_message",
    "update_user_data",
]
