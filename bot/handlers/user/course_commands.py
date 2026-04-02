"""
Ders yönetimi komutları.
"""

import logging
import sys

from telebot import types

from bot.handlers.user.audit import log_user_action, new_user_request_id
from bot.handlers.user.data_helpers import load_user_profile, load_user_snapshot
from bot.instance import bot_instance as bot
from common.background_tasks import submit_background_task
from common.config import get_user_session
from common.utils import (
    decrypt_password,
    escape_html,
    load_saved_grades,
    split_long_message,
    update_user_data,
)
from services.ninova import get_user_courses, login_to_ninova

logger = logging.getLogger("ninova")


def _resolve_main_callable(name: str):
    """Get callable from active runtime module first, then fallback import.

    This avoids re-import side effects when app is started as `python main.py`.
    """
    runtime_main = sys.modules.get("__main__")
    candidate = getattr(runtime_main, name, None) if runtime_main else None
    if callable(candidate):
        return candidate

    imported_main = sys.modules.get("main")
    if imported_main is None:
        import main as imported_main

    fallback = getattr(imported_main, name, None)
    return fallback if callable(fallback) else None


@bot.message_handler(commands=["otoders"])
def run_otoders_command(message):
    """Handle /otoders command by starting the auto-add flow."""
    trigger_auto_add_courses(
        str(message.chat.id),
        start_message="⏳ Oto Ders başlatıldı: dersleriniz otomatik olarak senkronize ediliyor...",
    )


@bot.message_handler(func=lambda message: message.text == "📖 Dersler")
def interactive_menu(message):
    """
    Etkileşimli ders menüsünü başlatır.

    Kullanıcı ders seçip detaylara (not, ödev, dosya, duyuru) erişebilir.
    Her ders için buton oluşturulur.

    :param message: Kullanıcıdan gelen /ders veya /dersler komutu
    """
    chat_id = str(message.chat.id)
    _user_data, user_grades, _urls = load_user_snapshot(chat_id, urls_source="grades")

    if not user_grades:
        bot.reply_to(message, "Henüz takip ettiğiniz ders yok. /otoders ile ekleyebilirsiniz.")
        return

    markup = types.InlineKeyboardMarkup()
    for i, (_url, data) in enumerate(user_grades.items()):
        course_name = data.get("course_name", "Bilinmeyen Ders")
        markup.add(types.InlineKeyboardButton(f"📚 {course_name}", callback_data=f"crs_{i}"))

    # Add general control button
    markup.add(types.InlineKeyboardButton("🔄 Tümünü Kontrol Et", callback_data="global_kontrol"))
    # Add Manual Course Menu button
    markup.add(
        types.InlineKeyboardButton("📝 Manuel Ders Yönetimi", callback_data="manual_menu_open")
    )

    bot.send_message(
        message.chat.id,
        "📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


def trigger_auto_add_courses(chat_id: str, request_id: str | None = None, start_message: str = ""):
    """Start auto-add flow for a user and optionally send a starter message."""
    request_id = request_id or new_user_request_id("otd")
    user_info = load_user_profile(chat_id)
    username = user_info.get("username")
    password = decrypt_password(user_info.get("password", ""))

    if not username or not password:
        log_user_action(chat_id, "otoders", status="missing_credentials", request_id=request_id)
        bot.send_message(
            chat_id,
            "❌ Kullanıcı adı veya şifre eksik! Lütfen önce 👤 Kullanıcı menüsünden giriş yapın.",
        )
        return

    logger.info(f"Oto Ders başlatıldı - Chat ID: {chat_id}, Kullanıcı Adı: {username}")
    log_user_action(chat_id, "otoders", status="started", request_id=request_id)
    if start_message:
        bot.send_message(chat_id, start_message)

    def run_auto_add():
        try:
            from datetime import datetime

            from services.ninova import get_class_info

            record_user_error = _resolve_main_callable("_record_user_error")
            check_user_updates_fn = _resolve_main_callable("check_user_updates")

            session = get_user_session(chat_id)
            if login_to_ninova(session, chat_id, username, password):
                courses = get_user_courses(session)
                if not courses:
                    log_user_action(chat_id, "otoders", status="no_courses", request_id=request_id)
                    bot.send_message(chat_id, "❌ Hiç aktif ders bulunamadı veya bir hata oluştu.")
                    return

                # --- Cleanup orphaned data for this user ---
                all_grades = load_saved_grades()
                user_grades = all_grades.get(chat_id, {})
                current_urls = set(user_info.get("urls", []))

                # Remove courses from data.json if they are not in user's url list
                courses_to_remove = [url for url in user_grades if url not in current_urls]
                if courses_to_remove:
                    for url in courses_to_remove:
                        del user_grades[url]
                    all_grades[chat_id] = user_grades

                    from common.utils import save_grades

                    save_grades(all_grades)
                # --- End cleanup ---

                already_in_data = []
                active_to_add = []
                expired_candidates = []

                # Mevcut dersleri listeye al
                new_urls_list = list(current_urls)

                # Yeni dersler için tarih kontrolü yapacağız
                # Mevcut dersler zaten 'current_urls' içinde, onları tekrar kontrol etmeye gerek yok

                now = datetime.now()

                for course in courses:
                    name, url = course["name"], course["url"]

                    if url in current_urls:
                        # Zaten ekli
                        already_in_data.append(name)
                        continue

                    # Yeni bir ders, tarihini kontrol et
                    # Eğer kullanıcı daha önce eklemişse (URL listesinde varsa) tekrar sormaya gerek yok
                    # Ama yukarıdaki if bunu check ediyor zaten.

                    # If class detail parsing fails for a single course, keep flow alive.
                    class_info = get_class_info(session, url) or {}
                    end_date = class_info.get("end_date")

                    is_expired = False
                    if end_date and end_date < now:
                        is_expired = True

                    if is_expired:
                        expired_candidates.append({"name": name, "url": url})
                    else:
                        active_to_add.append({"name": name, "url": url})
                        new_urls_list.append(url)

                log_user_action(
                    chat_id,
                    "otoders_scan",
                    status="completed",
                    request_id=request_id,
                    details=(
                        f"fetched={len(courses)};already={len(already_in_data)};"
                        f"active_new={len(active_to_add)};expired={len(expired_candidates)}"
                    ),
                )

                # 1. Aktif dersleri kaydet
                if active_to_add:
                    update_user_data(chat_id, "urls", new_urls_list)

                # 2. Rapor oluştur
                response = "📊 <b>Ders Tarama Sonucu</b>\n\n"

                if already_in_data:
                    response += "✅ <b>Zaten Ekli Dersler:</b>\n"
                    for name in already_in_data:
                        response += f"  • {escape_html(name)}\n"
                    response += "\n"

                if active_to_add:
                    response += "✨ <b>Yeni Eklenen Dersler:</b>\n"
                    for c in active_to_add:
                        response += f"  ➕ {escape_html(c['name'])}\n"
                    response += "\n🔄 Yeni dersler için senkronizasyon yapılıyor...\n"

                if not active_to_add and not already_in_data and not expired_candidates:
                    response += "ℹ️ Yeni eklenecek ders bulunamadı.\n"

                chunks = split_long_message(response)
                for chunk in chunks:
                    try:
                        bot.send_message(chat_id, chunk, parse_mode="HTML")
                    except Exception:
                        # Fallback to plain text if Telegram rejects HTML payload.
                        bot.send_message(chat_id, chunk)

                # 3. Aktif dersler için senkronizasyon
                if active_to_add and check_user_updates_fn:
                    result = check_user_updates_fn(chat_id, silent=True, request_id=request_id)
                    if result.get("success"):
                        log_user_action(
                            chat_id,
                            "otoders_sync",
                            status="completed",
                            request_id=request_id,
                            details=f"changes={result.get('changes', 0)}",
                        )
                        bot.send_message(
                            chat_id,
                            "✅ <b>Senkronizasyon Tamamlandı!</b>\n"
                            "Aktif dersleriniz listeye eklendi.",
                            parse_mode="HTML",
                        )
                    else:
                        log_user_action(
                            chat_id,
                            "otoders_sync",
                            status="failed",
                            request_id=request_id,
                            details=result.get("message", "unknown"),
                            level="warning",
                        )
                elif active_to_add and not check_user_updates_fn:
                    log_user_action(
                        chat_id,
                        "otoders_sync",
                        status="missing_sync_handler",
                        request_id=request_id,
                        level="warning",
                    )

                # 4. Eski dersler varsa sor
                if expired_candidates:
                    # Save candidates to user_data temporarily
                    expired_urls = [c["url"] for c in expired_candidates]
                    update_user_data(chat_id, "temp_expired_courses", expired_urls)

                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton(
                            "✅ Evet, Ekle", callback_data="add_expired_yes"
                        ),
                        types.InlineKeyboardButton("❌ Hayır", callback_data="add_expired_no"),
                    )

                    bot.send_message(
                        chat_id,
                        f"⚠️ <b>Dikkat:</b> Ninova sınıf listesinde tarihi geçmiş {len(expired_candidates)} eski dönem dersi bulundu.\n\n"
                        "Bunları da listenize eklemek ister misiniz?",
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
                    log_user_action(
                        chat_id,
                        "otoders",
                        status="awaiting_expired_confirmation",
                        request_id=request_id,
                        details=f"expired={len(expired_candidates)}",
                    )

                log_user_action(chat_id, "otoders", status="completed", request_id=request_id)

            else:
                logger.warning(f"Oto Ders giriş başarısız - Chat ID: {chat_id}")
                log_user_action(chat_id, "otoders", status="login_failed", request_id=request_id)
                if record_user_error:
                    record_user_error(
                        chat_id,
                        "LOGIN_FAILED",
                        "Oto ders akışında Ninova girişi başarısız",
                        username,
                    )
        except Exception as e:
            logger.error(f"Oto Ders sırasında hata oluştu ({chat_id}): {e}")
            log_user_action(
                chat_id,
                "otoders",
                status="failed",
                request_id=request_id,
                details=str(e),
                level="error",
            )
            record_user_error = _resolve_main_callable("_record_user_error")
            if record_user_error:
                record_user_error(chat_id, "OTODERS_EXCEPTION", str(e), username)
            bot.send_message(
                chat_id,
                "⚠️ Oto Ders sırasında bir hata oluştu. Lütfen /otoders ile tekrar deneyin.",
            )

    if not submit_background_task("auto_add_courses", run_auto_add):
        log_user_action(
            chat_id, "otoders", status="queue_full", request_id=request_id, level="warning"
        )
        bot.send_message(chat_id, "⏳ Sistem yoğun, lütfen biraz sonra tekrar deneyin.")
