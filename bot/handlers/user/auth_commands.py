"""Kullanıcı kimlik doğrulama komutları."""

import logging

from bot.instance import bot_instance as bot
from bot.keyboards import build_cancel_keyboard, build_main_keyboard
from bot.utils import is_cancel_text
from common.config import get_user_session
from common.utils import update_user_data
from services.ninova import get_user_courses, login_to_ninova

from .data_helpers import load_user_profile

logger = logging.getLogger("ninova")


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
    if is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard())
        return

    username = message.text.strip()
    if not username:
        bot.send_message(chat_id, "❌ Geçerli bir kullanıcı adı girmediniz.")
        return

    update_user_data(chat_id, "username", username)
    logger.info(f"Kullanıcı adı güncellendi - Chat ID: {chat_id}, Kullanıcı Adı: {username}")
    bot.send_message(
        chat_id,
        f"✅ Kullanıcı adı kaydedildi: <code>{username}</code>",
        parse_mode="HTML",
        reply_markup=build_main_keyboard(),
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
    if is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard())
        return

    password = message.text.strip()
    if not password:
        bot.send_message(chat_id, "❌ Geçerli bir şifre girmediniz.")
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logger.debug(f"[{chat_id}] Could not delete password message: {e}")

    chat_id_str = str(chat_id)
    user_info = load_user_profile(chat_id_str)
    username = (user_info.get("username") or "").strip()

    if not username:
        bot.send_message(
            chat_id,
            "❌ Önce kullanıcı adınızı girin: 👤 Kullanıcı Adı",
            reply_markup=build_main_keyboard(),
        )
        return

    checking_msg = bot.send_message(chat_id, "⏳ Giriş bilgileri doğrulanıyor...")
    user_session = get_user_session(chat_id_str)

    login_ok = login_to_ninova(user_session, chat_id_str, username, password, quiet=True)
    courses = get_user_courses(user_session) if login_ok else []

    try:
        bot.delete_message(chat_id, checking_msg.message_id)
    except Exception as e:
        logger.debug(f"[{chat_id}] Could not delete checking message: {e}")

    if not login_ok or not courses:
        logger.warning(f"Kimlik doğrulama başarısız - Chat ID: {chat_id}")
        bot.send_message(
            chat_id,
            "❌ Kullanıcı adı veya şifre hatalı. Lütfen bilgilerinizi kontrol edip tekrar deneyin.",
            reply_markup=build_main_keyboard(),
        )
        return

    update_user_data(chat_id, "password", password)
    logger.info(f"Şifre güncellendi ve doğrulandı - Chat ID: {chat_id}")

    bot.send_message(
        chat_id,
        "✅ Giriş başarılı. Şifreniz güvenli bir şekilde kaydedildi.",
        reply_markup=build_main_keyboard(),
    )
