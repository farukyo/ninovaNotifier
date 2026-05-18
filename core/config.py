"""Application configuration loaded from environment variables.

migrated from: common/config.py
AppConfig dataclass (Step 6 target) is defined here as a stub alongside
the migrated module-level globals and functions.
"""

# migrated from: common/config.py
from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from rich.console import Console

from core.cache import get_cache_manager
from core.http_client import get_session_manager

load_dotenv(Path("secrets") / ".env")
console = Console()
logger = logging.getLogger("ninova")

# Klasör ve Dosya Yolları
DATA_DIR = "data"
LOGS_DIR = "logs"
SECRETS_DIR = "secrets"

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
Path(SECRETS_DIR).mkdir(parents=True, exist_ok=True)

USERS_FILE = str(Path(DATA_DIR) / "users.json")
DATA_FILE = str(Path(DATA_DIR) / "ninova_data.json")

# Thread-safe dosya erişimi için lock'lar
_users_lock = threading.Lock()
_data_lock = threading.Lock()

# Şifreleme anahtarı (ENV'den veya varsayılan)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    KEY_FILE = Path(SECRETS_DIR) / ".encryption_key"
    if KEY_FILE.exists():
        with KEY_FILE.open("rb") as f:
            ENCRYPTION_KEY = f.read()
    else:
        ENCRYPTION_KEY = Fernet.generate_key()
        with KEY_FILE.open("wb") as f:
            f.write(ENCRYPTION_KEY)
        console.print("[yellow]⚠️ Yeni şifreleme anahtarı oluşturuldu: .encryption_key[/yellow]")

cipher_suite = Fernet(ENCRYPTION_KEY)


def _atomic_json_write(filepath, data):
    """
    JSON verisini atomik olarak dosyaya yazar.

    Önce geçici dosyaya yazar, sonra os.replace() ile hedef dosyaya taşır.
    Bu sayede yazma sırasında oluşabilecek kesintilerde veri kaybı önlenir.

    :param filepath: Hedef dosya yolu
    :param data: Yazılacak JSON-serializable veri
    """
    dir_name = Path(filepath).parent or "."
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_name), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        Path(tmp_path).replace(filepath)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()
        raise


def atomic_json_write(filepath, data):
    """Public wrapper for atomic JSON writes."""
    _atomic_json_write(filepath, data)


def load_all_users():
    """
    Tüm kullanıcı verilerini users.json dosyasından yükler (thread-safe).

    :return: Kullanıcı sözlüğü (chat_id: user_data) veya boş dict
    """
    with _users_lock:
        if Path(USERS_FILE).exists():
            try:
                with Path(USERS_FILE).open(encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.critical(f"{USERS_FILE} dosyası bozuk! Kontrol döngüsü atlanıyor.")
                console.print(f"[red bold]⚠️ {USERS_FILE} dosyası bozuk![/red bold]")
                return {}
        return {}


def save_all_users(users):
    """
    Tüm kullanıcı verilerini users.json dosyasına kaydeder (thread-safe, atomik).

    :param users: Kaydedilecek kullanıcı sözlüğü
    """
    with _users_lock:
        _atomic_json_write(USERS_FILE, users)


CHECK_INTERVAL = 300

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN")

# Çoklu admin desteği: virgülle ayrılmış ID listesi desteklenir
_raw_admin_ids = os.getenv("ADMIN_TELEGRAM_ID", "0")
ADMIN_TELEGRAM_IDS: list[int] = [
    int(x.strip()) for x in _raw_admin_ids.split(",") if x.strip().lstrip("-").isdigit()
]
ADMIN_TELEGRAM_ID: int = ADMIN_TELEGRAM_IDS[0] if ADMIN_TELEGRAM_IDS else 0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# SessionManager'ı başlat (TTL: 15 dakika, Max: 5000 oturum)
_session_manager = get_session_manager(ttl_seconds=15 * 60)

# CacheManager'ı başlat (Max: 10000 entry, TTL: 7 gün)
_cache_manager = get_cache_manager(max_entries=10000, ttl_seconds=7 * 24 * 3600)

USER_SESSIONS = {}


def get_user_session(chat_id: int):
    return _session_manager.get_session(chat_id, headers=HEADERS)


def close_user_session(chat_id: int) -> bool:
    return _session_manager.close_session(chat_id)


def cleanup_inactive_sessions(force: bool = False) -> int:
    return _session_manager.cleanup_inactive_sessions(force=force)


def get_session_stats() -> dict:
    return _session_manager.stats()


def has_user_session(chat_id: int) -> bool:
    return _session_manager.has_session(chat_id)


def get_active_user_sessions() -> list[int]:
    return _session_manager.get_active_sessions()


def get_cache_stats() -> dict:
    return _cache_manager.stats()


def sync_cache_to_disk() -> None:
    _cache_manager.sync()


# Sabitler
MAX_NOTIFIED_URLS = 500
MAX_ARI24_EVENTS = 200
MAX_SKS_MENU = 100

REQUEST_TIMEOUT = 15
REQUEST_TIMEOUT_LONG = 30

SESSION_CLEANUP_INTERVAL = 5 * 60
SESSION_TTL = 15 * 60

CACHE_FILE_TTL = 7 * 24 * 3600
CACHE_MAX_ENTRIES = 10000

MAX_LOGIN_RETRIES = 5
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_MAX = 60


# --- Step 6 target: AppConfig dataclass replaces module-level globals above ---


@dataclass
class AppConfig:
    """All tuneable parameters in one place. Instantiate via from_env()."""

    telegram_token: str = ""
    admin_telegram_ids: list[int] = field(default_factory=list)

    data_dir: Path = Path("data")
    logs_dir: Path = Path("logs")
    secrets_dir: Path = Path("secrets")

    check_interval_seconds: int = 300
    session_ttl_seconds: int = 900
    session_cleanup_interval_seconds: int = 300

    cache_max_entries: int = 10_000
    cache_ttl_seconds: int = 7 * 24 * 3600

    request_timeout_seconds: int = 15
    request_timeout_long_seconds: int = 30

    max_login_retries: int = 5
    retry_backoff_base: int = 2
    retry_backoff_max_seconds: int = 60

    max_notified_urls: int = 500

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment / .env file. Stub for Step 6."""
        raise NotImplementedError("Populate in Step 6")
