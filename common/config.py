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

# Global oturum belleği
USER_SESSIONS = {}
