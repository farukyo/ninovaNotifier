import contextlib
import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from rich.console import Console

from common.cache_manager import get_cache_manager
from common.session import get_session_manager

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
        # Hata durumunda geçici dosyayı temizle
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()
        raise


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
                logger.error(f"{USERS_FILE} dosyası bozuk!")
                console.print(f"[red]⚠️ {USERS_FILE} dosyası bozuk! Boş dict döndürülüyor.")
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
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ============================================================================
# Session ve Cache Yönetimi - SessionManager ve CacheManager ile
# ============================================================================

# SessionManager'ı başlat (TTL: 15 dakika, Max: 5000 oturum)
_session_manager = get_session_manager(ttl_seconds=15 * 60)

# CacheManager'ı başlat (Max: 10000 entry, TTL: 7 gün)
_cache_manager = get_cache_manager(max_entries=10000, ttl_seconds=7 * 24 * 3600)

# Backward compatibility: USER_SESSIONS referansı (ama SessionManager tarafından yönetilir)
# Eski kod hala USER_SESSIONS kullanabilir, ama asıl yönetim SessionManager'da olur
USER_SESSIONS = {}


def get_user_session(chat_id: int):
    """
    Kullanıcı için HTTP session alır (SessionManager tarafından yönetilir).

    :param chat_id: Kullanıcı chat ID
    :return: requests.Session nesnesi
    """
    return _session_manager.get_session(chat_id, headers=HEADERS)


def close_user_session(chat_id: int) -> bool:
    """
    Kullanıcı oturumunu kapat.

    :param chat_id: Kullanıcı chat ID
    :return: Başarılı kapatma durumu
    """
    return _session_manager.close_session(chat_id)


def cleanup_inactive_sessions(force: bool = False) -> int:
    """
    Inaktif oturumları temizle.

    :param force: Tüm oturumları kapat mı?
    :return: Temizlenen oturum sayısı
    """
    return _session_manager.cleanup_inactive_sessions(force=force)


def get_session_stats() -> dict:
    """Session yöneticisi istatistikleri döndür."""
    return _session_manager.stats()


def get_cache_stats() -> dict:
    """Cache yöneticisi istatistikleri döndür."""
    return _cache_manager.stats()


# ============================================================================
# Sabitler (Magic Numbers)
# ============================================================================

# Loglama ve Durum Dosyaları
MAX_NOTIFIED_URLS = 500  # Notified URLs liste sınırı
MAX_ARI24_EVENTS = 200  # Arı24 events cache sınırı
MAX_SKS_MENU = 100  # SKS menüsü cache sınırı

# Request Timeout'ları
REQUEST_TIMEOUT = 15  # requests.get() timeout (saniye)
REQUEST_TIMEOUT_LONG = 30  # Uzun işlemler için timeout

# Session Temizlik
SESSION_CLEANUP_INTERVAL = 5 * 60  # 5 dakikada bir temizlik
SESSION_TTL = 15 * 60  # 15 dakika

# Cache
CACHE_FILE_TTL = 7 * 24 * 3600  # 7 gün
CACHE_MAX_ENTRIES = 10000

# Retry Mekanizması
MAX_LOGIN_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff için base
RETRY_BACKOFF_MAX = 30  # max backoff (saniye)
