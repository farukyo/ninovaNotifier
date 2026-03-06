import urllib.parse

from telebot import types

from bot.instance import bot_instance as bot
from common.utils import escape_html, get_file_icon, load_saved_grades


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
        return None

    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in ("ninova.itu.edu.tr", "www.ninova.itu.edu.tr"):
        return None

    # Query string ve alt sayfa temizliği
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari", "/DersDosyalari"]:
        if clean_url.endswith(suffix):
            clean_url = clean_url[: -len(suffix)]
            break

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
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🎓 <b>{course_name}</b>\n<i>Dosya bulunamadı.</i>",
            parse_mode="HTML",
            reply_markup=markup,
        )
        return

    folders = set()
    file_entries = []
    prefix_len = len(path_segments)

    for real_idx, file in enumerate(files):
        segments = file.get("name", "").split("/")
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
        markup.add(
            types.InlineKeyboardButton(f"📁 {folder}", callback_data=f"dir_{course_idx}_{encoded}")
        )

    for real_idx, file in file_entries:
        basename = file["name"].split("/")[-1]
        icon = get_file_icon(basename)
        markup.add(
            types.InlineKeyboardButton(
                f"{icon} {basename}", callback_data=f"dl_{course_idx}_{real_idx}"
            )
        )

    if path_segments:
        parent = encode_path(path_segments[:-1])
        markup.add(
            types.InlineKeyboardButton("↩️ Üst klasör", callback_data=f"dir_{course_idx}_{parent}")
        )

    markup.add(types.InlineKeyboardButton("↩️ Ders menüsüne dön", callback_data=f"crs_{course_idx}"))

    path_label = "/" + "/".join(path_segments) if path_segments else "/"
    response = (
        f"🎓 <b>{course_name}</b>\n"
        f"📂 <b>Dosyalar</b>\nKonum: <code>{escape_html(path_label)}</code>\n"
        "(İndirmek için dosyaya tıklayın)"
    )

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=response,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
