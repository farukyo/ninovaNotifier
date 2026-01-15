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
    # Config
    "console",
    "USERS_FILE",
    "DATA_FILE",
    "ENCRYPTION_KEY",
    "cipher_suite",
    "load_all_users",
    "save_all_users",
    "CHECK_INTERVAL",
    "TELEGRAM_TOKEN",
    "HEADERS",
    "USER_SESSIONS",
    # Utils
    "parse_turkish_date",
    "encrypt_password",
    "decrypt_password",
    "update_user_data",
    "escape_html",
    "get_file_icon",
    "send_telegram_message",
    "send_telegram_document",
    "load_saved_grades",
    "save_grades",
]
