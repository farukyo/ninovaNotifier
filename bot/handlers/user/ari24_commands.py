import hashlib
import logging

from telebot import types

from bot.callback_parsing import callback_parse_fail, parse_int_part, split_callback_data
from bot.handlers.user.audit import log_user_action
from bot.instance import bot_instance as bot
from bot.keyboards import build_ari24_menu_keyboard
from core.config import load_all_users
from core.storage import modify_user
from services.ari24.client import Ari24Client

logger = logging.getLogger("ninova")
ari24_client = Ari24Client()
CLUBS_PER_PAGE = 10
# Telegram callback_data en fazla 64 *byte* olabilir. Türkçe karakterler UTF-8'de 2 byte
# tuttuğu için 40 karakterlik kesme yetmiyordu ve uzun kulüp adları tüm sayfanın
# gönderilmesini (BUTTON_DATA_INVALID) engelliyordu. "unsub_" öneki 6 byte.
# Anahtar = okunabilir önek + "~" + tam adın 8 haneli hash'i. Sadece önek kullanmak
# benzersiz değildi: ilk byte'ları aynı iki uzun kulüp adı aynı anahtarı üretiyor ve
# kullanıcı butondakinden farklı bir kulübe abone olabiliyordu.
_CLUB_HASH_LEN = 8
_CLUB_KEY_MAX_BYTES = 64 - len("unsub_")
_CLUB_PREFIX_MAX_BYTES = _CLUB_KEY_MAX_BYTES - len("~") - _CLUB_HASH_LEN


def _club_key(club: str) -> str:
    """Kulüp adından callback_data'ya sığan (≤ 58 byte) ve benzersiz bir anahtar üretir."""
    prefix = club.encode("utf-8")[:_CLUB_PREFIX_MAX_BYTES].decode("utf-8", errors="ignore")
    digest = hashlib.sha1(club.encode("utf-8")).hexdigest()[:_CLUB_HASH_LEN]
    return f"{prefix}~{digest}"


@bot.message_handler(func=lambda message: message.text == "🐝 Arı24")
def show_ari24_menu(message):
    chat_id = str(message.chat.id)
    log_user_action(chat_id, "ari24_menu")
    users = load_all_users()
    user_data = users.get(chat_id, {})
    daily_sub = user_data.get("daily_subscription", False)

    bot.send_message(
        message.chat.id,
        "🐝 <b>Arı24 Menüsü</b>\n\nBuradan İTÜ'deki etkinlikleri takip edebilirsiniz.",
        parse_mode="HTML",
        reply_markup=build_ari24_menu_keyboard(daily_sub),
    )


@bot.message_handler(func=lambda message: message.text == "🌍 Keşfet")
def discover_events(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🔄 Bu haftanın etkinlikleri çekiliyor, lütfen bekleyin...")

    events = ari24_client.get_weekly_events()

    if not events:
        bot.send_message(chat_id, "😔 Bu hafta için planlanmış etkinlik bulunamadı.")
        return

    count = 0
    for event in events:
        caption = (
            f"📅 <b>{event['title']}</b>\n"
            f"🏛 {event['organizer']}\n"
            f"🕒 {event['date_str']}\n"
            f"🔗 <a href='{event['link']}'>Detaylar</a>"
        )

        try:
            if event["image_url"]:
                bot.send_photo(chat_id, event["image_url"], caption=caption, parse_mode="HTML")
            else:
                bot.send_message(chat_id, caption, parse_mode="HTML")
            count += 1
        except Exception as e:
            logger.warning(f"Error sending event message: {e}")
            bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=False)
            count += 1

    # Refresh menu to current state
    users = load_all_users()
    daily_sub = users.get(str(chat_id), {}).get("daily_subscription", False)
    bot.send_message(
        chat_id,
        f"✅ Bu hafta toplam {count} etkinlik var.",
        reply_markup=build_ari24_menu_keyboard(daily_sub),
    )


@bot.message_handler(func=lambda message: message.text == "📰 Haberler")
def show_news(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "🔄 Haberler çekiliyor, lütfen bekleyin...")

    news = ari24_client.get_news(limit=5)

    if not news:
        bot.send_message(chat_id, "😔 Haber bulunamadı.")
        return

    for article in news:
        caption = f"📰 <b>{article['title']}</b>\n🔗 <a href='{article['link']}'>Haberi Oku</a>"

        try:
            if article.get("image_url"):
                bot.send_photo(chat_id, article["image_url"], caption=caption, parse_mode="HTML")
            else:
                bot.send_message(chat_id, caption, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, caption, parse_mode="HTML")

    # Refresh menu
    users = load_all_users()
    daily_sub = users.get(str(chat_id), {}).get("daily_subscription", False)
    bot.send_message(
        chat_id,
        f"✅ Son {len(news)} haber listelendi.",
        reply_markup=build_ari24_menu_keyboard(daily_sub),
    )


@bot.message_handler(func=lambda message: (message.text or "").startswith("☀️ Günlük Bülten"))
def toggle_daily_bulletin(message):
    chat_id = str(message.chat.id)
    users = load_all_users()

    if chat_id not in users:
        bot.send_message(chat_id, "Kullanıcı kaydı bulunamadı.")
        return

    # Yeni değer kilit içinde hesaplanır; eski kopyadan hesaplamak hızlı iki tıklamada
    # ikinci değişikliği kaybediyordu.
    def _toggle(data):
        data["daily_subscription"] = not data.get("daily_subscription", False)

    updated = modify_user(chat_id, _toggle)
    if updated is None:
        bot.send_message(chat_id, "Kullanıcı kaydı bulunamadı.")
        return
    new_status = updated["daily_subscription"]

    status_text = "açıldı" if new_status else "kapatıldı"
    msg = f"☀️ Günlük Bülten aboneliği <b>{status_text}</b>."
    if new_status:
        msg += "\nHer sabah 08:00'de güncel etkinlikleri alacaksınız."
    else:
        msg += "\nArtık günlük bildirim almayacaksınız."

    bot.send_message(
        chat_id,
        msg,
        parse_mode="HTML",
        reply_markup=build_ari24_menu_keyboard(new_status),
    )


@bot.message_handler(func=lambda message: message.text == "🔔 Abone Ol")
def subscribe_menu(message):
    show_clubs_page(message.chat.id, 0)


def show_clubs_page(chat_id, page):
    clubs = ari24_client.get_all_clubs()

    if not clubs:
        bot.send_message(chat_id, "Kayıtlı kulüp bulunamadı.")
        return

    total_pages = (len(clubs) + CLUBS_PER_PAGE - 1) // CLUBS_PER_PAGE
    start_idx = page * CLUBS_PER_PAGE
    end_idx = start_idx + CLUBS_PER_PAGE
    current_page_clubs = clubs[start_idx:end_idx]

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(club, callback_data=f"sub_{_club_key(club)}")
        for club in current_page_clubs
    ]

    markup.add(*buttons)

    # Navigation Buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Önceki", callback_data=f"page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton("Sonraki ➡️", callback_data=f"page_{page + 1}")
        )

    if nav_buttons:
        markup.row(*nav_buttons)

    bot.send_message(
        chat_id,
        f"🔔 <b>Abone Olmak İstediğiniz Kulübü Seçin (Sayfa {page + 1}/{total_pages}):</b>",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def callback_pagination(call):
    parts = split_callback_data(call.data)
    page = parse_int_part(parts, 1)
    if page is None or page < 0:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz sayfa.")
        return
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_clubs_page(call.message.chat.id, page)


@bot.callback_query_handler(func=lambda call: call.data.startswith("sub_"))
def callback_subscribe(call):
    club_name_truncated = call.data[4:]
    chat_id = str(call.message.chat.id)

    if chat_id not in load_all_users():
        bot.answer_callback_query(call.id, "Kullanıcı bulunamadı.")
        return

    # callback_data'da kulüp anahtarı var; tam adı kulüp listesinden bul. Bulunamazsa
    # (liste değişmiş veya eski buton) anahtarın kendisini kulüp adı diye kaydetme.
    all_clubs = ari24_client.get_all_clubs()
    matched_club = next((c for c in all_clubs if _club_key(c) == club_name_truncated), None)
    if matched_club is None:
        bot.answer_callback_query(call.id, "Kulüp bulunamadı, lütfen listeyi yeniden açın.")
        return

    already = False

    def _subscribe(data):
        nonlocal already
        subs = data.setdefault("subscriptions", [])
        if matched_club in subs:
            already = True
        else:
            subs.append(matched_club)

    if modify_user(chat_id, _subscribe) is None:
        bot.answer_callback_query(call.id, "Kullanıcı bulunamadı.")
        return
    if already:
        bot.answer_callback_query(call.id, "Zaten abonesiniz!")
    else:
        bot.answer_callback_query(call.id, f"✅ {matched_club} takip ediliyor!")


@bot.message_handler(func=lambda message: message.text == "❤️ Kulüplerim")
def my_clubs(message):
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    subs = user_data.get("subscriptions", [])

    if not subs:
        bot.send_message(chat_id, "📭 Henüz hiç bir kulübe abone değilsiniz.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for club in subs:
        markup.add(
            types.InlineKeyboardButton(
                f"❌ Abonelikten Çık: {club}", callback_data=f"unsub_{_club_key(club)}"
            )
        )

    bot.send_message(
        chat_id, "<b>Takip Ettiğiniz Kulüpler:</b>", reply_markup=markup, parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("unsub_"))
def callback_unsubscribe(call):
    club_name_truncated = call.data[6:]
    chat_id = str(call.message.chat.id)

    users = load_all_users()
    if chat_id in users:
        subs = users[chat_id].get("subscriptions", [])

        # Match truncated name to full name in subs
        matched_club = next((c for c in subs if _club_key(c) == club_name_truncated), None)

        if matched_club:

            def _unsubscribe(data):
                data["subscriptions"] = [
                    c for c in data.get("subscriptions", []) if c != matched_club
                ]

            modify_user(chat_id, _unsubscribe)
            bot.answer_callback_query(call.id, "Abonelikten çıkıldı.")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            bot.send_message(chat_id, f"✅ {matched_club} listeden çıkarıldı.")
        else:
            bot.answer_callback_query(call.id, "Abonelik bulunamadı.")
