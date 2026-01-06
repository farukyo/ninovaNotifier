"""
Core modülü - Sistem yapılandırması ve yardımcı fonksiyonlar.
"""

from core.config import (
    console,
    USERS_FILE,
    DATA_FILE,
    ENCRYPTION_KEY,
    cipher_suite,
    load_all_users,
    save_all_users,
    CHECK_INTERVAL,
    TELEGRAM_TOKEN,
    HEADERS,
    USER_SESSIONS,
)

from core.utils import (
    parse_turkish_date,
    encrypt_password,
    decrypt_password,
    update_user_data,
    escape_html,
    get_file_icon,
    send_telegram_message,
    send_telegram_document,
    load_saved_grades,
    save_grades,
)

from core.logic import (
    calculate_letter_grade,
    predict_course_performance,
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
    # Logic
    "calculate_letter_grade",
    "predict_course_performance",
]
