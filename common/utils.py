import json
import os
import re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from common.config import (
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
    """
    Şifreyi Fernet algoritması ile şifreler.

    :param password: Düz metin şifre
    :return: Şifrelenen şifre (string) veya boş string
    """
    if not password:
        return ""
    encrypted = cipher_suite.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password):
    """
    Şifrelenen şifreyi çözer.

    :param encrypted_password: Şifrelenen şifre string'i
    :return: Düz metin şifre veya hata durumunda orijinal değer
    """
    if not encrypted_password:
        return ""
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        return encrypted_password


def update_user_data(chat_id, key, value):
    """
    Kullanıcı verisini günceller. Password alanı için otomatik şifreleme yapar.

    :param chat_id: Kullanıcının Telegram chat ID'si
    :param key: Güncellenecek alan adı (username, password, urls vb.)
    :param value: Yeni değer
    :return: Güncellenmiş kullanıcı verisi
    """
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
    """
    HTML özel karakterlerini kaçırarak güvenli hale getirir.

    :param text: Kaçırılacak metin
    :return: Güvenli HTML metni
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sanitize_html_for_telegram(html_content):
    """
    Parses HTML content and returns a Telegram-safe version.
    Supports <b>, <i>, <a>, <code>, <pre>.
    Converts <p>, <div>, <br> and lists to appropriate spacing/bullet points.

    :param html_content: Raw HTML string
    :return: Telegram-safe HTML string
    """
    if not html_content:
        return ""

    try:
        # If it seems like plain text (no tags), just escape and return
        if "<" not in html_content and ">" not in html_content:
            return escape_html(html_content)

        soup = BeautifulSoup(html_content, "html.parser")

        def process_node(node):
            if isinstance(node, NavigableString):
                # Only escape text that isn't inside a tag we're processing
                return escape_html(str(node))

            if isinstance(node, Tag):
                name = node.name.lower()

                # Inline formatting tags Telegram supports
                if name in ("b", "strong"):
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<b>{inner}</b>"
                if name in ("i", "em"):
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<i>{inner}</i>"
                if name in ("u", "ins"):
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<u>{inner}</u>"
                if name in ("s", "strike", "del"):
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<s>{inner}</s>"
                if name == "code":
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<code>{inner}</code>"
                if name == "pre":
                    inner = "".join(process_node(c) for c in node.contents)
                    return f"<pre>{inner}</pre>"

                # Links
                if name == "a":
                    href = node.get("href", "")
                    # Ensure href is properly escaped/safe
                    href = href.replace('"', "%22")
                    if not href:
                        return "".join(process_node(c) for c in node.contents)
                    inner = "".join(process_node(c) for c in node.contents)
                    if not inner:
                        inner = href
                    return f'<a href="{href}">{inner}</a>'

                # Block elements -> spacing
                if name == "br":
                    return "\n"
                if name in (
                    "p",
                    "div",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "section",
                    "article",
                ):
                    inner = "".join(process_node(c) for c in node.contents).strip()
                    return f"{inner}\n\n" if inner else ""

                # Lists
                if name in ("ul", "ol"):
                    items = []
                    for li in node.find_all("li", recursive=False):
                        li_text = "".join(process_node(c) for c in li.contents).strip()
                        if li_text:
                            items.append(f"• {li_text}")
                    return "\n".join(items) + "\n\n" if items else ""

                if name == "li":
                    inner = "".join(process_node(c) for c in node.contents).strip()
                    return f"• {inner}\n" if inner else ""

                # Ignore other tags but keep their contents
                return "".join(process_node(c) for c in node.contents)

            return ""

        result = "".join(process_node(c) for c in soup.contents).strip()
        # Clean up excessive whitespace/newlines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result
    except Exception as e:
        console.print(f"[yellow]HTML Sanitization Error: {e}[/yellow]")
        # Fallback: simple text extract
        try:
            return escape_html(BeautifulSoup(html_content, "html.parser").get_text())
        except Exception:
            return escape_html(str(html_content))


def get_file_icon(filename):
    """
    Dosya uzantısına göre uygun emoji ikonunu döndürür.

    :param filename: Dosya adı (uzantı ile)
    :return: Dosya tipi için uygun emoji (varsayılan: 📄)
    """

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
    """
    Telegram botu üzerinden belirli bir kullanıcıya mesaj gönderir.
    Uzun mesajları otomatik olarak parçalara ayırır.

    :param chat_id: Telegram chat ID
    :param message: Gönderilecek mesaj metni (HTML formatında olabilir)
    :param is_error: Hata mesajı ise True, ön ek olarak uyarı ekler
    """
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
    """
    Telegram üzerinden dosya gönderir ve gönderim sonrası dosyayı siler.

    :param chat_id: Telegram chat ID
    :param filepath: Gönderilecek dosyanın yolu
    :param caption: Dosya ile birlikte gönderilecek açıklama metni
    """
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
    """
    Kaydedilmiş notları ninova_data.json dosyasından okur.

    :return: Not verileri sözlüğü (chat_id: grades) veya boş dict
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_grades(grades):
    """
    Notları ninova_data.json dosyasına kaydeder.

    :param grades: Kaydedilecek not verileri sözlüğü
    """
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, ensure_ascii=False, indent=4)
