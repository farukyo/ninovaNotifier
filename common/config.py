import logging
import os
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

# Yeni SQLite Veritabanı Yolu
DATABASE_FILE = str(Path(DATA_DIR) / "database.sqlite")

# Eski JSON yolları (sadece migration için tutulabilir, config'den kaldırıldı)
# USERS_FILE = str(Path(DATA_DIR) / "users.json")
# DATA_FILE = str(Path(DATA_DIR) / "ninova_data.json")

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
        console.print(
            "[yellow]⚠️ Yeni şifreleme anahtarı oluşturuldu: .encryption_key[/yellow]"
        )

cipher_suite = Fernet(ENCRYPTION_KEY)


CHECK_INTERVAL = 300

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Global oturum belleği
USER_SESSIONS = {}

