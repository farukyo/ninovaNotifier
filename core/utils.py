"""Utility functions: HTML helpers, crypto wrappers, date parsing, Telegram senders.

migrated from: common/utils.py
Storage functions (load_saved_grades, save_grades, update_user_data, delete_course_data)
are in core/storage.py but re-exported here for backward compatibility.
"""

from __future__ import annotations

import contextlib
import html
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from core.http_logging import http_request
from core.logger import log_with_context, redact_secrets
from core.storage import delete_course_data, load_saved_grades, save_grades, update_user_data

logger = logging.getLogger("ninova")

# Re-export storage symbols so callers of `common.utils` continue to work.
__all__ = [
    "decrypt_password",
    "delete_course_data",
    "encrypt_password",
    "escape_html",
    "get_assignment_status",
    "get_file_icon",
    "load_saved_grades",
    "parse_turkish_date",
    "sanitize_html_for_telegram",
    "save_grades",
    "send_telegram_document",
    "send_telegram_message",
    "split_long_message",
    "update_user_data",
]

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


def _turkish_lower(text: str) -> str:
    """Türkçe kurallarıyla küçük harfe çevirir (I→ı, İ→i); str.lower() "EKİM"i bozuyor."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def parse_turkish_date(date_str: str) -> datetime | None:
    """
    '10 Ekim 2025 14:30' veya '10 Ekim 2025' biçimindeki tarihleri parse eder.

    Saat yoksa 00:00 kabul edilir. Ay adı tanınmazsa None döner; eskiden sessizce
    Ocak ayı varsayılıyor ve ödev hatırlatmaları yanlış zamanda gidiyordu.
    """
    try:
        parts = date_str.strip().split()
        if len(parts) < 3:
            return None
        day = int(parts[0])
        month = DATE_MONTHS.get(_turkish_lower(parts[1]))
        year = int(parts[2])
        if month is None:
            logger.debug(f"Tarih parse hatası ('{date_str}'): bilinmeyen ay")
            return None
        hour = minute = 0
        if len(parts) >= 4 and ":" in parts[3]:
            time_parts = parts[3].split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1])
        return datetime(year, month, day, hour, minute)
    except (ValueError, IndexError, AttributeError) as e:
        logger.debug(f"Tarih parse hatası ('{date_str}'): {e}")
    return None


def encrypt_password(password: str) -> str:
    """Şifreyi global cipher_suite ile şifreler (asıl uygulama: core.crypto)."""
    from core.config import cipher_suite  # deferred to avoid import-time side effects
    from core.crypto import encrypt_password as _encrypt

    return _encrypt(cipher_suite, password)


def decrypt_password(encrypted_password: str) -> str | None:
    """Şifrelenmiş şifreyi global cipher_suite ile çözer (asıl uygulama: core.crypto)."""
    from core.config import cipher_suite  # deferred to avoid import-time side effects
    from core.crypto import decrypt_password as _decrypt

    return _decrypt(cipher_suite, encrypted_password)


def escape_html(text: str) -> str:
    """HTML özel karakterlerini kaçırarak güvenli hale getirir."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_attr(text: str) -> str:
    """HTML nitelik değeri (ör. href='...') için kaçırma; tırnakları da kaçırır."""
    return escape_html(text).replace('"', "&quot;").replace("'", "&#39;")


def sanitize_html_for_telegram(html_content: str) -> str:
    """Parses HTML content and returns a Telegram-safe version."""
    if not html_content:
        return ""

    try:
        if "<" not in html_content and ">" not in html_content:
            return escape_html(html_content)

        soup = BeautifulSoup(html_content, "html.parser")

        def process_node(node: Any) -> str:
            if isinstance(node, NavigableString):
                return escape_html(str(node))

            if isinstance(node, Tag):
                name = node.name.lower()

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
                if name == "a":
                    href = node.get("href", "")
                    href = href.replace('"', "%22")
                    if not href:
                        return "".join(process_node(c) for c in node.contents)
                    inner = "".join(process_node(c) for c in node.contents)
                    if not inner:
                        inner = href
                    return f'<a href="{href}">{inner}</a>'
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

                return "".join(process_node(c) for c in node.contents)

            return ""

        result = "".join(process_node(c) for c in soup.contents).strip()
        return re.sub(r"\n{3,}", "\n\n", result)
    except Exception as e:
        from core.config import console

        console.print(f"[yellow]HTML Sanitization Error: {e}[/yellow]")
        try:
            return escape_html(BeautifulSoup(html_content, "html.parser").get_text())
        except Exception:
            return escape_html(str(html_content))


def get_file_icon(filename: str) -> str:
    """Dosya uzantısına göre uygun emoji ikonunu döndürür."""
    icons = {
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
        "zip": "📦",
        "rar": "📦",
        "7z": "📦",
        "tar": "📦",
        "gz": "📦",
        "bz2": "📦",
        "arsiv": "📦",
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
        "mp4": "🎬",
        "avi": "🎬",
        "mov": "🎬",
        "mkv": "🎬",
        "wmv": "🎬",
        "flv": "🎬",
        "webm": "🎬",
        "video": "🎬",
        "mp3": "🎵",
        "wav": "🎵",
        "ogg": "🎵",
        "flac": "🎵",
        "aac": "🎵",
        "m4a": "🎵",
        "audio": "🎵",
        "ses": "🎵",
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
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    return icons.get(ext, "📄")


def get_assignment_status(assignment_dict: dict) -> tuple[str, bool]:
    """Calculates the status icon and active state of an assignment."""
    is_submitted = assignment_dict.get("is_submitted", False)
    end_date_str = assignment_dict.get("end_date", "")

    if is_submitted:
        return "✅", False

    due_date = parse_turkish_date(end_date_str)
    if not due_date:
        return "⚪", True

    now = datetime.now()
    delta = due_date - now
    days_left = delta.total_seconds() / (3600 * 24)

    if days_left < 0:
        return "❌", False
    if days_left <= 3:
        return "⚠️", True
    return "🟡", True


def split_long_message(text: str, limit: int = 4000) -> list[str]:
    """Splits a long message into chunks respecting newline boundaries."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split("\n"):
        if len(line) > limit:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            chunks.extend(line[i : i + limit] for i in range(0, len(line), limit))
            continue

        if len(current_chunk) + len(line) + 1 > limit:
            # Boş parça ekleme (tam limit uzunluğundaki ilk satırda oluyordu).
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += ("\n" if current_chunk else "") + line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def send_telegram_message(chat_id: Any, message: str, is_error: bool = False) -> None:
    """Telegram botu üzerinden belirli bir kullanıcıya mesaj gönderir."""
    from core.config import TELEGRAM_TOKEN, console  # deferred

    if not TELEGRAM_TOKEN or not chat_id:
        return

    prefix = "⚠️ <b>HATA</b>\n\n" if is_error else ""
    full_message = prefix + message
    # Telegram sınırı 4096; HTML etiketleri için pay bırakılır.
    messages = split_long_message(full_message, limit=3500)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for msg in messages:
        if not msg.strip():
            continue
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
        try:
            response = _post_telegram_message(url, chat_id, payload)
            if response.status_code == 400 and "can't parse entities" in response.text:
                # Uzun mesaj bölünürken bir HTML etiketi ikiye ayrılmış olabilir; bildirimi
                # tamamen kaybetmek yerine etiketsiz düz metin olarak gönder.
                plain = html.unescape(re.sub(r"<[^>]*>", "", msg))
                response = _post_telegram_message(url, chat_id, {"chat_id": chat_id, "text": plain})
            if response.status_code == 200:
                clean_msg = re.sub(r"<[^>]*>", "", msg.splitlines()[0])
                console.print(f"[green][Telegram] Mesaj gönderildi ({chat_id}): {clean_msg}")
            else:
                log_with_context(
                    logger,
                    "error",
                    "Telegram mesaj gonderme hatasi",
                    chat_id=str(chat_id),
                    action="telegram_send",
                    http_status=response.status_code,
                )
                console.print(f"[red][Telegram] Hata ({chat_id}): {response.text}")
        except requests.RequestException as e:
            log_with_context(
                logger,
                "error",
                f"Telegram mesaj gonderim ag hatasi: {redact_secrets(str(e))}",
                chat_id=str(chat_id),
                action="telegram_send",
                error_stage="http",
            )
            console.print(f"[red][Telegram] Gönderim hatası ({chat_id}): {redact_secrets(str(e))}")


def _post_telegram_message(url: str, chat_id: Any, payload: dict) -> requests.Response:
    """sendMessage isteği atar; 429 (rate limit) yanıtında bir kez bekleyip tekrar dener."""
    response = http_request(
        logger,
        requests,
        "POST",
        url,
        action="telegram_send",
        chat_id=str(chat_id),
        json=payload,
        timeout=10,
    )
    if response.status_code == 429:
        retry_after = 5
        with contextlib.suppress(ValueError, KeyError, TypeError):
            retry_after = int(response.json()["parameters"]["retry_after"])
        time.sleep(min(retry_after, 60))
        response = http_request(
            logger,
            requests,
            "POST",
            url,
            action="telegram_send",
            chat_id=str(chat_id),
            json=payload,
            timeout=10,
            retry_count=1,
        )
    return response


def send_telegram_document(
    chat_id: Any,
    document: Any,
    caption: str = "",
    filename: str = "document.pdf",
    is_file_id: bool = False,
) -> str | None:
    """Telegram üzerinden dosya gönderir. Path, BytesIO veya File ID destekler."""
    from core.config import TELEGRAM_TOKEN, console  # deferred

    if not TELEGRAM_TOKEN or not chat_id:
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    sent_file_id = None

    try:
        if is_file_id:
            data = {
                "chat_id": chat_id,
                "document": document,
                "caption": caption,
                "parse_mode": "HTML",
            }
            response = http_request(
                logger,
                requests,
                "POST",
                url,
                action="telegram_send_document",
                chat_id=str(chat_id),
                data=data,
                timeout=30,
            )
        elif isinstance(document, str) and Path(document).exists():
            filename = Path(document).name
            with Path(document).open("rb") as f:
                files = {"document": (filename, f)}
                data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
                response = http_request(
                    logger,
                    requests,
                    "POST",
                    url,
                    action="telegram_send_document",
                    chat_id=str(chat_id),
                    data=data,
                    files=files,
                    timeout=60,
                )
            with contextlib.suppress(OSError):
                Path(document).unlink()
        else:
            if hasattr(document, "seek"):
                document.seek(0)
            files = {"document": (filename, document)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = http_request(
                logger,
                requests,
                "POST",
                url,
                action="telegram_send_document",
                chat_id=str(chat_id),
                data=data,
                files=files,
                timeout=60,
            )

        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("ok"):
                doc = resp_json["result"].get("document")
                if doc:
                    sent_file_id = doc.get("file_id")
            console.print(f"[green][Telegram] Dosya gönderildi ({chat_id}): {filename}")
        else:
            log_with_context(
                logger,
                "error",
                "Telegram dosya gonderim hatasi",
                chat_id=str(chat_id),
                action="telegram_send_document",
                http_status=response.status_code,
            )
            console.print(f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {response.text}")

    except Exception as e:
        log_with_context(
            logger,
            "error",
            f"Telegram dosya gonderim istisnasi: {redact_secrets(str(e))}",
            chat_id=str(chat_id),
            action="telegram_send_document",
            exc_info=True,
        )
        console.print(
            f"[red][Telegram] Dosya gönderim hatası ({chat_id}): {redact_secrets(str(e))}"
        )

    return sent_file_id
