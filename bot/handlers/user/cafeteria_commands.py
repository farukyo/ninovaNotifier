import logging
from datetime import datetime

from telebot import types

from bot.callback_parsing import callback_parse_fail, split_callback_data
from bot.handlers.user.audit import log_user_action
from bot.instance import bot_instance as bot
from core.scheduler import submit_background_task
from services.sks.scraper import get_meal_menu

logger = logging.getLogger("ninova")


@bot.message_handler(func=lambda message: message.text == "🍽 Yemekhane")
def send_cafeteria_menu(message):
    """
    Shows the current day's cafeteria menu with a refresh button.
    """
    log_user_action(str(message.chat.id), "cafeteria_menu")
    now = datetime.now()
    # If before 15:00, show lunch by default, else show dinner
    slot = "lunch" if now.hour < 15 else "dinner"
    chat_id = message.chat.id

    def _send_menu():
        # SKS isteği 15 sn'ye kadar sürebiliyor; polling thread'i bloklanmasın.
        menu_text = get_meal_menu(meal_type=slot) or "⚠️ Yemek listesi alınamadı."
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Güncelle", callback_data=f"cafeteria_refresh_{slot}")
        )
        bot.send_message(chat_id, menu_text, reply_markup=markup, parse_mode="HTML")

    if not submit_background_task("cafeteria_menu", _send_menu):
        bot.send_message(chat_id, "⏳ Sistem yoğun, lütfen biraz sonra tekrar deneyin.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("cafeteria_refresh_"))
def handle_cafeteria_refresh(call):
    """
    Refreshes the cafeteria menu message with the latest data.
    """
    parts = split_callback_data(call.data)
    if len(parts) < 3:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz menü isteği."
        )
        return

    slot = parts[2]
    if slot not in {"lunch", "dinner"}:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz öğün.")
        return

    # Show user that something is happening
    bot.answer_callback_query(call.id, "Menü güncelleniyor...")
    if not submit_background_task("cafeteria_refresh", _refresh_menu, call, slot):
        logger.warning("Cafeteria refresh skipped: background queue full")


def _refresh_menu(call, slot: str) -> None:
    menu_text = get_meal_menu(meal_type=slot) or "⚠️ Yemek listesi alınamadı."

    # Add refresh timestamp footer
    now_str = datetime.now().strftime("%H:%M:%S")
    menu_text += f"\n\n🔄 <i>Son Güncelleme: {now_str}</i>"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Güncelle", callback_data=f"cafeteria_refresh_{slot}"))

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=menu_text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug(f"Cafeteria message update skipped: {e}")
