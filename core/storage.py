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
    from core.config import cipher_suite  # deferred to avoid circular import
    from core.crypto import encrypt_password

    with _users_lock:
        users = _read_json(USERS_FILE)
        if users is None:
            # Bozuk dosyayı {} ile ezip tüm kullanıcıları silmek yerine işlemi iptal et.
            raise RuntimeError(f"{USERS_FILE} bozuk; kullanıcı verisi güncellenemedi")

        chat_id = str(chat_id)
        if chat_id not in users:
            users[chat_id] = {"username": "", "password": "", "urls": []}

        if key == "password":
            value = encrypt_password(cipher_suite, value)
        users[chat_id][key] = value
        atomic_json_write(USERS_FILE, users)
        return users[chat_id]


# ---------------------------------------------------------------------------
# Grade / course data
# ---------------------------------------------------------------------------


def modify_user(chat_id, mutator) -> dict | None:
    """
    Tek bir kullanıcının kaydını kilit altında oku-değiştir-yaz yapar.

    load_all_users() + save_all_users() ikilisi arada başka bir thread yazarsa onun
    değişikliğini ezer; bu fonksiyon tüm işlemi tek kilit altında yapar.

    :param chat_id: Kullanıcının Telegram chat ID'si
    :param mutator: Kullanıcı dict'ini yerinde değiştiren fonksiyon
    :return: Güncellenmiş kullanıcı verisi, kullanıcı yoksa None
    """
    chat_id = str(chat_id)
    with _users_lock:
        users = _read_json(USERS_FILE)
        if users is None or chat_id not in users:
            return None
        mutator(users[chat_id])
        atomic_json_write(USERS_FILE, users)
        return users[chat_id]


def delete_user(chat_id) -> bool:
    """Kullanıcı kaydını kilit altında siler."""
    chat_id = str(chat_id)
    with _users_lock:
        users = _read_json(USERS_FILE)
        if not users or chat_id not in users:
            return False
        del users[chat_id]
        atomic_json_write(USERS_FILE, users)
        return True


def _read_json(path: str) -> dict | None:
    """JSON dosyasını okur; dosya yoksa {}, bozuksa None döner (üzerine yazılmasın diye)."""
    if not Path(path).exists():
        return {}
    try:
        with Path(path).open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.critical(f"{path} dosyası bozuk! Yazma işlemi iptal edildi.")
        return None


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


def update_user_grades(chat_id, course_data: dict) -> None:
    """
    Bir kullanıcının ders verilerini kilit altında günceller.

    Tüm dosyanın eski bir kopyasını kaydetmek, arada başka kullanıcılar için yazılan
    verileri ezer (ve sonraki kontrolde aynı bildirimlerin tekrar gitmesine yol açar).
    Bu fonksiyon dosyayı kilit altında yeniden okuyup sadece bu kullanıcının
    derslerini günceller.

    :param chat_id: Kullanıcının Telegram chat ID'si
    :param course_data: {course_url: ders_verisi} — mevcut kayıtların üzerine yazılır
    """
    chat_id = str(chat_id)
    with _data_lock:
        all_grades = _read_json(DATA_FILE)
        if all_grades is None:
            raise RuntimeError(f"{DATA_FILE} bozuk; ders verisi kaydedilemedi")
        all_grades.setdefault(chat_id, {}).update(course_data)
        atomic_json_write(DATA_FILE, all_grades)


def delete_user_grades(chat_id) -> bool:
    """Bir kullanıcının tüm ders verilerini kilit altında siler."""
    chat_id = str(chat_id)
    with _data_lock:
        all_grades = _read_json(DATA_FILE)
        if not all_grades or chat_id not in all_grades:
            return False
        del all_grades[chat_id]
        atomic_json_write(DATA_FILE, all_grades)
        return True


def delete_course_data(chat_id, course_url: str) -> bool:
    """
    Belirli bir dersin verilerini ninova_data.json dosyasından siler.
    migrated from: common/utils.py
    """
    chat_id = str(chat_id)
    with _data_lock:
        all_grades = _read_json(DATA_FILE)
        if not all_grades or course_url not in all_grades.get(chat_id, {}):
            return False
        del all_grades[chat_id][course_url]
        if not all_grades[chat_id]:
            del all_grades[chat_id]
        atomic_json_write(DATA_FILE, all_grades)
        return True
