"""Application configuration loaded from environment variables.

migrated from: common/config.py
"""

# migrated from: common/config.py
from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from rich.console import Console

from core.cache import get_cache_manager
from core.http_client import SessionManager, get_session_manager

load_dotenv(Path("secrets") / ".env")
console = Console()
logger = logging.getLogger("ninova")

# Klasör ve Dosya Yolları
DATA_DIR = "data"
LOGS_DIR = "logs"
SECRETS_DIR = "secrets"  # pragma: allowlist secret

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
Path(SECRETS_DIR).mkdir(parents=True, exist_ok=True)

# users.json / ninova_data.json erişimi core.storage üzerinden yapılır. Eskiden burada
# ayrı kilitlerle ikinci bir kopya vardı; iki farklı kilit aynı dosyayı koruduğu için
# eşzamanlı yazmalar birbirini ezebiliyordu. Tek kaynak: core.storage.
from core.storage import (  # noqa: E402, F401 — geriye dönük uyumluluk için re-export
    DATA_FILE,
    USERS_FILE,
    atomic_json_write,
    load_all_users,
    save_all_users,
)

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


# Rehber (İTÜ SSO) oturumları Ninova oturumlarından ayrı tutulur: RehberScraper oturuma
# POST'u da tekrar deneyen bir retry adapter'ı takıyor. Hesap değişince/silinince
# close_user_session ikisini birden kapatır; yoksa eski hesabın Rehber girişi
# 15 dakikaya kadar yeniden kullanılabiliyordu.
_rehber_session_manager = SessionManager(ttl_seconds=15 * 60)


def get_user_session(chat_id: int):
    return _session_manager.get_session(chat_id, headers=HEADERS)


def get_rehber_session(chat_id):
    return _rehber_session_manager.get_session(chat_id, headers=HEADERS)


def close_user_session(chat_id: int) -> bool:
    _rehber_session_manager.close_session(chat_id)
    return _session_manager.close_session(chat_id)


def cleanup_inactive_sessions(force: bool = False) -> int:
    _rehber_session_manager.cleanup_inactive_sessions(force=force)
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
