"""Kullanıcı kimlik doğrulama komutları."""

import logging

from bot.instance import bot_instance as bot
from bot.keyboards import build_cancel_keyboard, build_main_keyboard
from bot.utils import is_cancel_text
from core.config import close_user_session, get_user_session
from core.utils import update_user_data
from services.ninova import LoginFailedError, get_user_courses, login_to_ninova

from .audit import log_user_action
from .course_commands import trigger_auto_add_courses

logger = logging.getLogger("ninova")


@bot.message_handler(func=lambda message: message.text == "🔐 Giriş Yap")
def start_login_flow(message):
    """
    Kullanıcıdan sırayla kullanıcı adı ve şifreyi alır.
    """
    log_user_action(str(message.chat.id), "login_start")
    prompt = bot.send_message(
        message.chat.id,
        "✏️ Lütfen kullanıcı adınızı yazın:",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_login_username)


def process_login_username(message):
    chat_id = message.chat.id
    if is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard())
        return

    username = (message.text or "").strip()
    if not username:
        bot.send_message(chat_id, "❌ Geçerli bir kullanıcı adı girmediniz.")
        return

    prompt = bot.send_message(
        chat_id,
        "🔒 Lütfen şifrenizi yazın (gönderdiğiniz mesaj otomatik silinecek):",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, lambda msg: process_login_password(msg, username))


def process_login_password(message, username):
    chat_id = message.chat.id
    if is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard())
        return

    password = (message.text or "").strip()
    if not password:
        bot.send_message(chat_id, "❌ Geçerli bir şifre girmediniz.")
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logger.debug(f"[{chat_id}] Could not delete password message: {e}")

    chat_id_str = str(chat_id)
    username = (username or "").strip()

    checking_msg = bot.send_message(chat_id, "⏳ Giriş bilgileri doğrulanıyor...")
    # Eski (başka hesapla açılmış olabilecek) oturumu kapat; aksi halde login_to_ninova
    # "oturum zaten aktif" deyip yeni bilgileri hiç doğrulamadan kabul ediyordu.
    close_user_session(chat_id_str)
    user_session = get_user_session(chat_id_str)

    login_error_type = None
    try:
        login_ok = login_to_ninova(user_session, chat_id_str, username, password, quiet=True)
        courses = get_user_courses(user_session) if login_ok else []
    except LoginFailedError as e:
        # Hatalı şifrede login_to_ninova False dönmek yerine exception fırlatıyor;
        # yakalanmadığında kullanıcı hiçbir yanıt alamıyordu.
        logger.info(f"[{chat_id_str}] Login failed: {e.error_type}")
        login_ok, courses, login_error_type = False, [], e.error_type

    try:
        bot.delete_message(chat_id, checking_msg.message_id)
    except Exception as e:
        logger.debug(f"[{chat_id}] Could not delete checking message: {e}")

    if not login_ok or not courses:
        log_user_action(chat_id_str, "login", status="failed", level="warning")
        if login_error_type in (None, "INVALID_CREDENTIALS"):
            fail_text = (
                "❌ Kullanıcı adı veya şifre hatalı. "
                "Lütfen bilgilerinizi kontrol edip tekrar deneyin."
            )
        else:
            fail_text = "⚠️ Ninova'ya şu anda ulaşılamıyor. Lütfen biraz sonra tekrar deneyin."
        bot.send_message(chat_id, fail_text, reply_markup=build_main_keyboard())
        return

    update_user_data(chat_id, "username", username)
    update_user_data(chat_id, "password", password)
    update_user_data(chat_id, "daily_subscription", True)
    log_user_action(chat_id_str, "login", status="success", details=f"username={username}")

    bot.send_message(
        chat_id,
        "✅ Giriş başarılı. Bilgileriniz güvenli şekilde kaydedildi.\n🤖 Oto Ders otomatik başlatılıyor...",
        reply_markup=build_main_keyboard(),
    )

    trigger_auto_add_courses(
        chat_id_str,
        start_message="⏳ Oto Ders başlatıldı: dersleriniz otomatik olarak senkronize ediliyor...",
    )
