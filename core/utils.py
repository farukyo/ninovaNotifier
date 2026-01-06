import json
import os
import re
import requests
from core.config import (
    TELEGRAM_TOKEN,
    DATA_FILE,
    console,
    load_all_users,
    save_all_users,
    cipher_suite,
)
from datetime import datetime

DATE_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}


def parse_turkish_date(date_str):
    """
    Parses dates like '10 Ekim 2025 00:00' or '06 Ekim 2025 10:54'
    Returns datetime object or None
    """
    try:
        parts = date_str.strip().split()
        if len(parts) >= 4:
            day = int(parts[0])
            month_name = parts[1].lower()  # Case insensitive yapıldı
            year = int(parts[2])
            time_parts = parts[3].split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1])

            month = DATE_MONTHS.get(month_name, 1)
            return datetime(year, month, day, hour, minute)
    except Exception:
        # Hata ayıklama için print eklenebilir, fakat sessiz kalması tercih edilmiş.
        pass
    return None


def encrypt_password(password):
    """Şifreyi encrypt eder."""
    if not password:
        return ""
    encrypted = cipher_suite.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password):
    """Şifreyi decrypt eder."""
    if not encrypted_password:
        return ""
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        return encrypted_password


def update_user_data(chat_id, key, value):
    """Kullanıcı verisini günceller. password ise şifreler."""
    users = load_all_users()
    chat_id = str(chat_id)
    if chat_id not in users:
        users[chat_id] = {"username": "", "password": "", "urls": []}

    if key == "password":
        value = encrypt_password(value)
    users[chat_id][key] = value
    save_all_users(users)
    return users[chat_id]


def escape_html(text):
    """HTML özel karakterlerini kaçırır."""
    if not isinstance(text, str):
        return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_file_icon(filename):
    """Dosya uzantısına göre ikon döner."""

    # Tüm desteklenen uzantı/tip -> emoji eşleşmeleri
    icons = {
        # Dökümanlar
        "pdf": "📕",
        "doc": "📘",
        "docx": "📘",
        "odt": "📘",
        "word": "📘",
        "xls": "📗",
        "xlsx": "📗",
        "ods": "📗",
        "csv": "📗",
        "excel": "📗",
        "ppt": "📙",
        "pptx": "📙",
        "odp": "📙",
        "powerpoint": "📙",
        "txt": "📝",
        "rtf": "📝",
        "text": "📝",
        "md": "📝",
        # Arşivler
        "zip": "📦",
        "rar": "📦",
        "7z": "📦",
        "tar": "📦",
        "gz": "📦",
        "bz2": "📦",
        "arsiv": "📦",
        # Görseller
        "jpg": "🖼️",
        "jpeg": "🖼️",
        "png": "🖼️",
        "gif": "🖼️",
        "bmp": "🖼️",
        "svg": "🖼️",
        "webp": "🖼️",
        "ico": "🖼️",
        "resim": "🖼️",
        "image": "🖼️",
        "img": "🖼️",
        # Videolar
        "mp4": "🎬",
        "avi": "🎬",
        "mov": "🎬",
        "mkv": "🎬",
        "wmv": "🎬",
        "flv": "🎬",
        "webm": "🎬",
        "video": "🎬",
        # Ses
        "mp3": "🎵",
        "wav": "🎵",
        "ogg": "🎵",
        "flac": "🎵",
        "aac": "🎵",
        "m4a": "🎵",
        "audio": "🎵",
        "ses": "🎵",
        # Kod dosyaları
        "py": "🐍",
        "js": "📜",
        "ts": "📜",
        "code": "📜",
        "html": "🌐",
        "htm": "🌐",
        "css": "🎨",
        "java": "☕",
        "c": "⚙️",
        "cpp": "⚙️",
        "h": "⚙️",
        "hpp": "⚙️",
        "s": "⚙️",
        "asm": "⚙️",
        "exe": "⚙️",
        "dll": "⚙️",
        "so": "⚙️",
        "cs": "🔷",
        "go": "🐹",
        "rs": "🦀",
        "rb": "💎",
        "php": "🐘",
        "swift": "🍎",
        "kt": "🟣",
        "scala": "🔴",
        "r": "📊",
        "m": "📐",
        "mat": "📐",
        "tex": "📐",
        "sql": "🗃️",
        "json": "📋",
        "xml": "📋",
        "yaml": "📋",
        "yml": "📋",
        "sh": "🖥️",
        "bat": "🖥️",
        "ps1": "🖥️",
        "hex": "🔢",
        "bin": "🔢",
        "ipynb": "📓",
        "bib": "📚",
    }

    if not isinstance(filename, str):
        return "📄"

    # Dosya adından uzantıyı kontrol et
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    return icons.get(ext, "📄")


def send_telegram_message(chat_id, message, is_error=False):
    """Telegram botu üzerinden belirli bir kullanıcıya mesaj gönderir. Uzun mesajları parçalara ayırır."""
    if not TELEGRAM_TOKEN or not chat_id:
        return

    prefix = "⚠️ <b>HATA</b>\n\n" if is_error else ""
    full_message = prefix + message

    # Telegram limit: 4096 characters. Use 3500 to be safe with HTML tags.
    LIMIT = 3500
    messages = []

    if len(full_message) <= LIMIT:
        messages.append(full_message)
    else:
        # Mesajı satır bazlı böl
        lines = full_message.split("\n")
        current_msg = ""
        for line in lines:
            # Eğer tek bir satır limitin üzerindeyse (çok nadir), onu da karakter bazlı böl
            if len(line) > LIMIT:
                if current_msg:
                    messages.append(current_msg)
                    current_msg = ""
                # Satırı parçala
                for i in range(0, len(line), LIMIT):
                    messages.append(line[i : i + LIMIT])
                continue

            if len(current_msg) + len(line) + 1 > LIMIT:
                if current_msg:
                    messages.append(current_msg)
                current_msg = line
            else:
                current_msg += ("\n" if current_msg else "") + line

        if current_msg:
            messages.append(current_msg)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for msg in messages:
        if not msg.strip():
            continue
        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                clean_msg = re.sub(r"<[^>]*>", "", msg.splitlines()[0])
                console.print(
                    f"[green][Telegram] Mesaj gönderildi ({chat_id}): {clean_msg}"
                )
            else:
                console.print(f"[red][Telegram] Hata ({chat_id}): {response.text}")
        except Exception as e:
            console.print(f"[red][Telegram] Gönderim hatası ({chat_id}): {e}")


def send_telegram_document(chat_id, filepath, caption=""):
    """Telegram üzerinden dosya gönderir ve sonra dosyayı siler."""
    if not TELEGRAM_TOKEN or not chat_id or not os.path.exists(filepath):
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            files = {"document": (filename, f)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, data=data, files=files)

        if response.status_code == 200:
            console.print(
                f"[green][Telegram] Dosya gönderildi ({chat_id}): {os.path.basename(filepath)}"
            )
        else:
            console.print(
                f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {response.text}"
            )
    except Exception as e:
        console.print(f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {e}")
    finally:
        # Dosyayı her durumda sil
        if os.path.exists(filepath):
            os.remove(filepath)


def load_saved_grades():
    """Kaydedilmiş notları dosyadan okur."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_grades(grades):
    """Notları dosyaya kaydeder."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, ensure_ascii=False, indent=4)
