"""
Kullanıcı kimlik doğrulama komutları.
"""

import contextlib

from bot.instance import bot_instance as bot
from bot.keyboards import build_cancel_keyboard, build_main_keyboard
from common.utils import update_user_data


def _is_cancel_text(text: str) -> bool:
    """Check if the message text indicates a cancel action."""
    if not text:
        return False
    t = text.strip().lower()
    return "iptal" in t or "cancel" in t or "⛔" in text


@bot.message_handler(func=lambda message: message.text == "👤 Kullanıcı Adı")
def set_username(message):
    """
    Kullanıcıdan yeni bir mesaj olarak kullanıcı adını ister.
    """
    prompt = bot.send_message(
        message.chat.id,
        "✏️ Lütfen kullanıcı adınızı yazın:",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_username)


def process_username(message):
    chat_id = message.chat.id
    if _is_cancel_text(message.text):
        bot.send_message(
            chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard(chat_id)
        )
        return

    username = message.text.strip()
    if not username:
        bot.send_message(chat_id, "❌ Geçerli bir kullanıcı adı girmediniz.")
        return

    update_user_data(chat_id, "username", username)
    bot.send_message(
        chat_id,
        f"✅ Kullanıcı adı kaydedildi: <code>{username}</code>",
        parse_mode="HTML",
        reply_markup=build_main_keyboard(chat_id),
    )


@bot.message_handler(func=lambda message: message.text == "🔐 Şifre")
def set_password(message):
    """
    Kullanıcıdan yeni bir mesaj olarak şifreyi ister.
    """
    prompt = bot.send_message(
        message.chat.id,
        "🔒 Lütfen şifrenizi yazın (gönderdiğiniz mesaj otomatik silinecek):",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_password)


def process_password(message):
    chat_id = message.chat.id
    if _is_cancel_text(message.text):
        bot.send_message(
            chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard(chat_id)
        )
        return

    password = message.text.strip()
    if not password:
        bot.send_message(chat_id, "❌ Geçerli bir şifre girmediniz.")
        return

    update_user_data(chat_id, "password", password)
    with contextlib.suppress(Exception):
        bot.delete_message(chat_id, message.message_id)

    bot.send_message(
        chat_id,
        "✅ Şifreniz güvenli bir şekilde kaydedildi.",
        reply_markup=build_main_keyboard(chat_id),
    )
