from telebot import types

from bot.instance import bot_instance as bot
from bot.keyboards import build_ari24_menu_keyboard
from common.config import load_all_users, save_all_users
from services.ari24.client import Ari24Client

ari24_client = Ari24Client()
CLUBS_PER_PAGE = 10


@bot.message_handler(func=lambda message: message.text == "🐝 Arı24")
def show_ari24_menu(message):
    chat_id = str(message.chat.id)
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
            print(f"Error sending event message: {e}")
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


@bot.message_handler(func=lambda message: message.text.startswith("☀️ Günlük Bülten"))
def toggle_daily_bulletin(message):
    chat_id = str(message.chat.id)
    users = load_all_users()

    if chat_id not in users:
        bot.send_message(chat_id, "Kullanıcı kaydı bulunamadı.")
        return

    current_status = users[chat_id].get("daily_subscription", False)
    new_status = not current_status
    users[chat_id]["daily_subscription"] = new_status
    save_all_users(users)

    status_text = "açıldı" if new_status else "kapatıldı"
    bot.send_message(
        chat_id,
        f"☀️ Günlük Bülten aboneliği <b>{status_text}</b>.\n"
        "Her sabah 08:00'de o günün etkinlikleri size gönderilecek.",
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
    buttons = []

    for club in current_page_clubs:
        safe_name = club[:40]  # Truncate for callback data limit safety
        buttons.append(types.InlineKeyboardButton(club, callback_data=f"sub_{safe_name}"))

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
    page = int(call.data.split("_")[1])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_clubs_page(call.message.chat.id, page)


@bot.callback_query_handler(func=lambda call: call.data.startswith("sub_"))
def callback_subscribe(call):
    club_name_truncated = call.data[4:]
    chat_id = str(call.message.chat.id)

    users = load_all_users()
    if chat_id not in users:
        bot.answer_callback_query(call.id, "Kullanıcı bulunamadı.")
        return

    user_data = users[chat_id]
    subs = user_data.get("subscriptions", [])

    # We need to find full name from truncated name if possible,
    # OR just rely on what we have.
    # Since we use get_all_clubs(), we can try to match.
    # But callback data is limited.
    # Let's search in all clubs list for a match.

    all_clubs = ari24_client.get_all_clubs()
    matched_club = next(
        (c for c in all_clubs if c[:40] == club_name_truncated), club_name_truncated
    )

    if matched_club in subs:
        bot.answer_callback_query(call.id, "Zaten abonesiniz!")
    else:
        subs.append(matched_club)
        user_data["subscriptions"] = subs
        save_all_users(users)
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
                f"❌ Abonelikten Çık: {club}", callback_data=f"unsub_{club[:40]}"
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
        user_data = users[chat_id]
        subs = user_data.get("subscriptions", [])

        # Match truncated name to full name in subs
        matched_club = next((c for c in subs if c[:40] == club_name_truncated), None)

        if matched_club:
            subs.remove(matched_club)
            user_data["subscriptions"] = subs
            save_all_users(users)
            bot.answer_callback_query(call.id, "Abonelikten çıkıldı.")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            bot.send_message(chat_id, f"✅ {matched_club} listeden çıkarıldı.")
        else:
            bot.answer_callback_query(call.id, "Abonelik bulunamadı.")
