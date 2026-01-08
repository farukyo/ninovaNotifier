import os
import json
from dotenv import load_dotenv
from rich.console import Console
from cryptography.fernet import Fernet

load_dotenv()
console = Console()

# Klasör ve Dosya Yolları
DATA_DIR = "data"
LOGS_DIR = "logs"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
DATA_FILE = os.path.join(DATA_DIR, "ninova_data.json")

# Şifreleme anahtarı (ENV'den veya varsayılan)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    KEY_FILE = ".encryption_key"
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            ENCRYPTION_KEY = f.read()
    else:
        ENCRYPTION_KEY = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(ENCRYPTION_KEY)
        console.print(
            "[yellow]⚠️ Yeni şifreleme anahtarı oluşturuldu: .encryption_key[/yellow]"
        )

cipher_suite = Fernet(ENCRYPTION_KEY)


def load_all_users():
    """
    Tüm kullanıcı verilerini users.json dosyasından yükler.

    :return: Kullanıcı sözlüğü (chat_id: user_data) veya boş dict
    """
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_all_users(users):
    """
    Tüm kullanıcı verilerini users.json dosyasına kaydeder.

    :param users: Kaydedilecek kullanıcı sözlüğü
    """
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


CHECK_INTERVAL = 300


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Global oturum belleği
USER_SESSIONS = {}
