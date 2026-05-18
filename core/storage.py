"""User data and grade data persistence (JSON, atomic writes, thread-safe).

migrated from:
  common/config.py  — load_all_users, save_all_users, _atomic_json_write
  common/utils.py   — load_saved_grades, save_grades, update_user_data,
                      delete_course_data
"""

# migrated from: common/config.py, common/utils.py
from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger("ninova")

# Thread-safe file access locks (mirrors common/config.py)
_users_lock = threading.Lock()
_data_lock = threading.Lock()

USERS_FILE = str(Path("data") / "users.json")
DATA_FILE = str(Path("data") / "ninova_data.json")


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def atomic_json_write(filepath, data) -> None:
    """
    JSON verisini atomik olarak dosyaya yazar.
    migrated from: common/config.py (_atomic_json_write / atomic_json_write)
    """
    dir_name = Path(filepath).parent or Path()
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_name), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        Path(tmp_path).replace(filepath)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()
        raise


# ---------------------------------------------------------------------------
# User data
# ---------------------------------------------------------------------------


def load_all_users() -> dict:
    """
    Tüm kullanıcı verilerini users.json dosyasından yükler (thread-safe).
    migrated from: common/config.py
    """
    with _users_lock:
        if Path(USERS_FILE).exists():
            try:
                with Path(USERS_FILE).open(encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.critical(f"{USERS_FILE} dosyası bozuk! Kontrol döngüsü atlanıyor.")
                return {}
        return {}


def save_all_users(users: dict) -> None:
    """
    Tüm kullanıcı verilerini users.json dosyasına kaydeder (thread-safe, atomik).
    migrated from: common/config.py
    """
    with _users_lock:
        atomic_json_write(USERS_FILE, users)


def update_user_data(chat_id, key: str, value) -> dict:
    """
    Kullanıcı verisini günceller. Password alanı için otomatik şifreleme yapar.
    migrated from: common/utils.py

    :param chat_id: Kullanıcının Telegram chat ID'si
    :param key: Güncellenecek alan adı
    :param value: Yeni değer
    :return: Güncellenmiş kullanıcı verisi
    """
    from core.crypto import encrypt_password  # deferred to avoid circular import

    with _users_lock:
        if Path(USERS_FILE).exists():
            try:
                with Path(USERS_FILE).open(encoding="utf-8") as f:
                    users = json.load(f)
            except json.JSONDecodeError:
                users = {}
        else:
            users = {}

        chat_id = str(chat_id)
        if chat_id not in users:
            users[chat_id] = {"username": "", "password": "", "urls": []}

        if key == "password":
            value = encrypt_password(value)
        users[chat_id][key] = value
        atomic_json_write(USERS_FILE, users)
        return users[chat_id]


# ---------------------------------------------------------------------------
# Grade / course data
# ---------------------------------------------------------------------------


def load_saved_grades() -> dict:
    """
    Kaydedilmiş notları ninova_data.json dosyasından okur (thread-safe).
    migrated from: common/utils.py
    """
    with _data_lock:
        if Path(DATA_FILE).exists():
            try:
                with Path(DATA_FILE).open(encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"{DATA_FILE} dosyası bozuk!")
                return {}
        return {}


def save_grades(grades: dict) -> None:
    """
    Notları ninova_data.json dosyasına kaydeder (thread-safe, atomik).
    migrated from: common/utils.py
    """
    with _data_lock:
        atomic_json_write(DATA_FILE, grades)


def delete_course_data(chat_id, course_url: str) -> bool:
    """
    Belirli bir dersin verilerini ninova_data.json dosyasından siler.
    migrated from: common/utils.py
    """
    chat_id = str(chat_id)
    all_grades = load_saved_grades()

    if chat_id in all_grades:
        user_grades = all_grades[chat_id]
        if course_url in user_grades:
            del user_grades[course_url]
            if not user_grades:
                del all_grades[chat_id]
            else:
                all_grades[chat_id] = user_grades
            save_grades(all_grades)
            return True
    return False
