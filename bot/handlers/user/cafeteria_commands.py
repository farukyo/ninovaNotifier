from datetime import datetime

from telebot import types

from bot.instance import bot_instance as bot
from services.sks.scraper import get_meal_menu


@bot.message_handler(func=lambda message: message.text == "🍽 Yemekhane")
def send_cafeteria_menu(message):
    """
    Shows the current day's cafeteria menu with a refresh button.
    """
    now = datetime.now()
    # If before 15:00, show lunch by default, else show dinner
    slot = "lunch" if now.hour < 15 else "dinner"

    menu_text = get_meal_menu(meal_type=slot)
    if not menu_text:
        menu_text = "⚠️ Yemek listesi alınamadı."

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Güncelle", callback_data=f"cafeteria_refresh_{slot}"))

    bot.send_message(message.chat.id, menu_text, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("cafeteria_refresh_"))
def handle_cafeteria_refresh(call):
    """
    Refreshes the cafeteria menu message with the latest data.
    """
    slot = call.data.split("_")[2]

    # Show user that something is happening
    bot.answer_callback_query(call.id, "Menü güncelleniyor...")

    menu_text = get_meal_menu(meal_type=slot)
    if not menu_text:
        menu_text = "⚠️ Yemek listesi alınamadı."

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
    except Exception:
        # If text hasn't changed, Telegram API raises an error. We can ignore it or notify.
        # But since we added a timestamp, the text SHOULD always change.
        pass
