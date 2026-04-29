import logging
import secrets
import threading
import time
import urllib.parse
from collections import OrderedDict

from telebot import types

from bot.instance import bot_instance as bot
from common.log_context import log_with_context
from common.utils import escape_html, get_file_icon, load_saved_grades

logger = logging.getLogger("ninova")

_PATH_TOKEN_TTL_SECONDS = 60 * 60
_PATH_TOKEN_MAX_ENTRIES = 2000
_PATH_TOKEN_LOCK = threading.Lock()
_PATH_TOKEN_CACHE: OrderedDict[str, tuple[str, float]] = OrderedDict()


def is_cancel_text(text: str) -> bool:
    """
    Kullanıcı mesajının iptal komutu olup olmadığını kontrol eder.

    :param text: Kullanıcı mesajı
    :return: İptal komutu ise True
    """
    if not text:
        return False
    t = text.strip().lower()
    return "iptal" in t or "cancel" in t or "⛔" in text


def validate_ninova_url(url: str) -> str | None:
    """
    Ninova URL'sini doğrular ve temizler. SSRF saldırılarını önler.

    :param url: Kontrol edilecek URL
    :return: Temizlenmiş URL veya geçersizse None
    """
    if not url:
        logger.debug("URL validation failed: empty URL")
        return None

    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in ("ninova.itu.edu.tr", "www.ninova.itu.edu.tr"):
        logger.warning(f"Invalid Ninova URL: {parsed.netloc}")
        return None

    # Query string ve alt sayfa temizliği
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari", "/DersDosyalari"]:
        if clean_url.endswith(suffix):
            clean_url = clean_url[: -len(suffix)]
            break

    logger.debug(f"Validated Ninova URL: {clean_url}")
    return clean_url


def encode_path(path_segments):
    """
    Dosya yolu segmentlerini URL uyumlu hale getirir ve birleştirir.

    :param path_segments: Klasör isimleri listesi (['dersler', 'notlar'])
    :return: URL-encoded string (dersler%2Fnotlar)
    """
    return urllib.parse.quote("/".join(path_segments))


def decode_path(path_str):
    """
    URL-encoded dosya yolunu tekrar segment listesine çevirir.

    :param path_str: URL-encoded string
    :return: Klasör isimleri listesi
    """
    return [p for p in urllib.parse.unquote(path_str).split("/") if p]


def _log_callback_size(callback_data: str, chat_id: str, action: str) -> None:
    if len(callback_data) > 64:
        log_with_context(
            logger,
            "warning",
            "callback_data length exceeds Telegram limit",
            chat_id=str(chat_id),
            action=action,
            callback_data_len=len(callback_data),
        )


def store_path_token(chat_id: str, message_id: int, encoded_path: str) -> str:
    """Store a short-lived token for a file browser path."""
    now = time.time()
    token = secrets.token_hex(4)
    key = f"{chat_id}:{message_id}:{token}"
    with _PATH_TOKEN_LOCK:
        while key in _PATH_TOKEN_CACHE:
            token = secrets.token_hex(4)
            key = f"{chat_id}:{message_id}:{token}"
        _PATH_TOKEN_CACHE[key] = (encoded_path, now)
        _PATH_TOKEN_CACHE.move_to_end(key)

        # Cleanup expired entries and enforce size limits.
        expired = [
            k for k, (_, ts) in _PATH_TOKEN_CACHE.items() if now - ts > _PATH_TOKEN_TTL_SECONDS
        ]
        for k in expired:
            del _PATH_TOKEN_CACHE[k]
        while len(_PATH_TOKEN_CACHE) > _PATH_TOKEN_MAX_ENTRIES:
            _PATH_TOKEN_CACHE.popitem(last=False)

    return token


def resolve_path_token(chat_id: str, message_id: int, token: str) -> str | None:
    """Resolve a stored path token for the file browser."""
    key = f"{chat_id}:{message_id}:{token}"
    now = time.time()
    with _PATH_TOKEN_LOCK:
        entry = _PATH_TOKEN_CACHE.get(key)
        if not entry:
            return None
        encoded_path, ts = entry
        if now - ts > _PATH_TOKEN_TTL_SECONDS:
            del _PATH_TOKEN_CACHE[key]
            return None
        _PATH_TOKEN_CACHE.move_to_end(key)
        return encoded_path


def show_file_browser(chat_id, message_id, course_idx, path_str=""):
    """
    Ders için klasör tabanlı dosya tarayıcısını gösterir.
    Klasörler ve dosyalar arasında gezinmeyi sağlar.

    :param chat_id: Kullanıcının chat ID'si
    :param message_id: Güncellenecek mesajın ID'si
    :param course_idx: Dersin indeks numarası
    :param path_str: Mevcut klasör yolu (URL-encoded)
    """
    path_segments = decode_path(path_str) if path_str else []

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if course_idx >= len(urls):
        return

    course_url = urls[course_idx]
    data = user_grades[course_url]
    files = data.get("files", [])
    course_name = data.get("course_name", "Bilinmeyen Ders")

    if not files:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("↩️ Ders menüsüne dön", callback_data=f"crs_{course_idx}")
        )
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"🎓 <b>{course_name}</b>\n<i>Dosya bulunamadı.</i>",
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception as e:
            logger.warning(f"show_file_browser edit failed ({chat_id}): {e}")
        return

    source_folder_map = {
        "Sınıf": "Sınıf Dosyaları",
        "Ders": "Ders Dosyaları",
    }

    folders = set()
    file_entries = []
    prefix_len = len(path_segments)

    for real_idx, file in enumerate(files):
        source_folder = source_folder_map.get(file.get("source"), "Diğer Dosyalar")
        segments = [source_folder, *file.get("name", "").split("/")]
        if len(segments) <= prefix_len:
            continue
        if segments[:prefix_len] != path_segments:
            continue

        if len(segments) == prefix_len + 1:
            file_entries.append((real_idx, file))
        else:
            folders.add(segments[prefix_len])

    # Limit files to last 50
    file_entries = file_entries[-50:]

    markup = types.InlineKeyboardMarkup()

    for folder in sorted(folders):
        encoded = encode_path([*path_segments, folder])
        token = store_path_token(str(chat_id), message_id, encoded)
        callback_data = f"dir_{course_idx}_{token}"
        _log_callback_size(callback_data, str(chat_id), "file_browser_dir")
        markup.add(types.InlineKeyboardButton(f"📁 {folder}", callback_data=callback_data))

    for real_idx, file in file_entries:
        basename = file["name"].split("/")[-1]
        icon = get_file_icon(basename)
        callback_data = f"dl_{course_idx}_{real_idx}"
        _log_callback_size(callback_data, str(chat_id), "file_browser_download")
        markup.add(types.InlineKeyboardButton(f"{icon} {basename}", callback_data=callback_data))

    if path_segments:
        parent = encode_path(path_segments[:-1])
        token = store_path_token(str(chat_id), message_id, parent)
        callback_data = f"dir_{course_idx}_{token}"
        _log_callback_size(callback_data, str(chat_id), "file_browser_dir")
        markup.add(types.InlineKeyboardButton("↩️ Üst klasör", callback_data=callback_data))

    callback_data = f"crs_{course_idx}"
    _log_callback_size(callback_data, str(chat_id), "file_browser_back")
    markup.add(types.InlineKeyboardButton("↩️ Ders menüsüne dön", callback_data=callback_data))

    path_label = "/" + "/".join(path_segments) if path_segments else "/"
    response = (
        f"🎓 <b>{course_name}</b>\n"
        f"📂 <b>Dosyalar</b>\nKonum: <code>{escape_html(path_label)}</code>\n"
        "(İndirmek için dosyaya tıklayın)"
    )

    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=response,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"show_file_browser edit failed ({chat_id}): {e}")
