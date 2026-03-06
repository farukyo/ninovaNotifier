import contextlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from common.config import (
    DATA_FILE,
    TELEGRAM_TOKEN,
    _atomic_json_write,
    _data_lock,
    cipher_suite,
    console,
    load_all_users,
    save_all_users,
)

logger = logging.getLogger("ninova")

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
    except (ValueError, IndexError, AttributeError) as e:
        logger.debug(f"Tarih parse hatası ('{date_str}'): {e}")
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
    :return: Düz metin şifre veya hata durumunda None
    """
    if not encrypted_password:
        return ""
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        logger.error("Şifre çözme başarısız! Şifreleme anahtarı değişmiş olabilir.")
        return None


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
        return re.sub(r"\n{3,}", "\n\n", result)
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


def get_assignment_status(assignment_dict):
    """
    Calculates the status icon and active state of an assignment.

    :param assignment_dict: The assignment dictionary containing 'is_submitted' and 'end_date'
    :return: tuple (status_icon, is_active_future_assignment)
    """
    is_submitted = assignment_dict.get("is_submitted", False)
    end_date_str = assignment_dict.get("end_date", "")

    # ✅ If submitted, always show green check
    if is_submitted:
        return (
            "✅",
            False,
        )  # It is completed, so 'active' depending on context, but here we treat it as fine.
        # Wait, if submitted, user wants to see it? "active" usually means "ToDo".
        # But let's check the requirement: "Show only active (future) assignments".
        # If I submitted it, it's done. Should it be hidden by default?
        # User said: "ödev tamamlandıysa ✅göstersin".
        # Usually completed assignments are good to see.
        # Let's consider 'active' = 'not expired OR submitted'.
        # If expired and not submitted -> ❌ (Hidden by default)

    # Convert date
    due_date = parse_turkish_date(end_date_str)
    if not due_date:
        # Cannot parse, treat as neutral
        return "⚪", True

    now = datetime.now()
    delta = due_date - now
    days_left = delta.total_seconds() / (3600 * 24)

    if days_left < 0:
        # ❌ Expired (and not submitted, captured above)
        return "❌", False  # Expired -> Not active
    if days_left <= 3:
        # ⚠️ Warning
        return "⚠️", True
    # 🟡 Info
    return "🟡", True


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
    limit = 3500
    messages = []

    if len(full_message) <= limit:
        messages.append(full_message)
    else:
        # Mesajı satır bazlı böl
        lines = full_message.split("\n")
        current_msg = ""
        for line in lines:
            # Eğer tek bir satır limitin üzerindeyse (çok nadir), onu da karakter bazlı böl
            if len(line) > limit:
                if current_msg:
                    messages.append(current_msg)
                    current_msg = ""
                # Satırı parçala
                messages.extend(line[i : i + limit] for i in range(0, len(line), limit))
                continue

            if len(current_msg) + len(line) + 1 > limit:
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
                console.print(f"[green][Telegram] Mesaj gönderildi ({chat_id}): {clean_msg}")
            else:
                logger.error(f"Telegram mesaj gönderme hatası ({chat_id}): {response.text}")
                console.print(f"[red][Telegram] Hata ({chat_id}): {response.text}")
        except requests.RequestException as e:
            logger.error(f"Telegram mesaj gönderim ağ hatası ({chat_id}): {e}")
            console.print(f"[red][Telegram] Gönderim hatası ({chat_id}): {e}")


def send_telegram_document(
    chat_id, document, caption="", filename="document.pdf", is_file_id=False
):
    """
    Telegram üzerinden dosya gönderir. Path, BytesIO veya File ID destekler.

    :param chat_id: Telegram chat ID
    :param document: Dosya yolu (str), BytesIO nesnesi veya File ID (str)
    :param caption: Dosya açıklaması
    :param filename: Dosya adı (BytesIO kullanılıyorsa gereklidir)
    :param is_file_id: True ise document parametresi File ID olarak işlenir
    :return: Gönderilen dosyanın file_id'si veya None
    """
    if not TELEGRAM_TOKEN or not chat_id:
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    sent_file_id = None

    try:
        # 1. Send by File ID
        if is_file_id:
            data = {
                "chat_id": chat_id,
                "document": document,
                "caption": caption,
                "parse_mode": "HTML",
            }
            response = requests.post(url, data=data, timeout=30)

        # 2. Send by File Path
        elif isinstance(document, str) and Path(document).exists():
            filename = Path(document).name
            with Path(document).open("rb") as f:
                files = {"document": (filename, f)}
                data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
                response = requests.post(url, data=data, files=files, timeout=60)

            # Delete temp file if it was a path
            with contextlib.suppress(OSError):
                Path(document).unlink()

        # 3. Send by BytesIO / Buffer
        else:
            # Assume document is a file-like object (BytesIO)
            if hasattr(document, "seek"):
                document.seek(0)
            files = {"document": (filename, document)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, data=data, files=files, timeout=60)

        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("ok"):
                doc = resp_json["result"].get("document")
                if doc:
                    sent_file_id = doc.get("file_id")

            console.print(f"[green][Telegram] Dosya gönderildi ({chat_id}): {filename}")
        else:
            logger.error(f"Telegram dosya gönderim hatası ({chat_id}): {response.text}")
            console.print(f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {response.text}")

    except Exception as e:
        logger.error(f"Telegram dosya gönderim istisnası ({chat_id}): {e}")
        console.print(f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {e}")

    return sent_file_id


def load_saved_grades():
    """
    Kaydedilmiş notları ninova_data.json dosyasından okur (thread-safe).

    :return: Not verileri sözlüğü (chat_id: grades) veya boş dict
    """
    with _data_lock:
        if Path(DATA_FILE).exists():
            try:
                with Path(DATA_FILE).open(encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"{DATA_FILE} dosyası bozuk!")
                console.print(f"[red]⚠️ {DATA_FILE} dosyası bozuk! Boş dict döndürülüyor.")
                return {}
        return {}


def save_grades(grades):
    """
    Notları ninova_data.json dosyasına kaydeder (thread-safe, atomik).

    :param grades: Kaydedilecek not verileri sözlüğü
    """
    with _data_lock:
        _atomic_json_write(DATA_FILE, grades)


def split_long_message(text, limit=4000):
    """
    Splits a long message into chunks while respecting newline boundaries to avoid breaking HTML tags.
    Default Telegram limit is 4096, but we use 4000 to be safe.

    :param text: The text to split.
    :param limit: Maximum characters per chunk.
    :return: List of text chunks.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    current_chunk = ""

    lines = text.split("\n")
    for line in lines:
        # If a single line is too long, force split it (rare case)
        if len(line) > limit:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # Split line by chars
            chunks.extend(line[i : i + limit] for i in range(0, len(line), limit))
            continue

        # Check if adding this line would exceed the limit
        # +1 accounts for the newline character we'll eventually need to join with (or implicit newlines)
        if len(current_chunk) + len(line) + 1 > limit:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def delete_course_data(chat_id, course_url):
    """
    Belirli bir dersin verilerini (not, ödev vb.) ninova_data.json dosyasından siler.

    :param chat_id: Kullanıcı ID
    :param course_url: Silinecek dersin URL'i
    """
    chat_id = str(chat_id)
    all_grades = load_saved_grades()

    if chat_id in all_grades:
        user_grades = all_grades[chat_id]
        if course_url in user_grades:
            del user_grades[course_url]
            # Eğer kullanıcının hiç dersi kalmadıysa, kullanıcı kaydını da data'dan silebiliriz (opsiyonel)
            if not user_grades:
                del all_grades[chat_id]
            else:
                all_grades[chat_id] = user_grades

            save_grades(all_grades)
            return True
    return False
