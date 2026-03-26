"""
Admin callback handler'ları.
"""

import contextlib
import logging
import os
import sys

from telebot import types

from bot.callback_parsing import callback_parse_fail, split_callback_data
from bot.instance import bot_instance as bot
from bot.instance import get_check_callback
from common.background_tasks import submit_background_task
from common.config import (
    cleanup_inactive_sessions,
    close_user_session,
    get_user_session,
    load_all_users,
    save_all_users,
)
from common.utils import (
    decrypt_password,
    load_saved_grades,
    save_grades,
    update_user_data,
)
from services.ninova import get_user_courses, login_to_ninova

from .helpers import is_admin, set_admin_state
from .services import send_backup, show_logs, show_stats, show_user_details

logger = logging.getLogger("ninova")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("adm_")
    and not call.data.startswith("adm_coursemgmt_")
    and not call.data.startswith("adm_delcourse_")
    and not call.data.startswith("adm_delconf_")
    and not call.data.startswith("adm_clearcourses_")
    and call.data != "adm_manage_courses"
)
def handle_admin_callbacks(call):
    """
    Admin panel callback'lerini yönetir.

    Admin panel butonlarından gelen tüm callback'leri işler:
    - stats: İstatistikler
    - users: Kullanıcı detayları
    - broadcast: Duyuru gönderme
    - msg: Mesaj gönderme
    - force: Manuel kontrol
    - forceoto: Ders listesi güncelleme
    - logs: Log görüntüleme
    - backup: Yedek alma
    - optout: Kullanıcı silme
    - restart: Sistem yeniden başlatma

    :param call: CallbackQuery nesnesi
    """
    if not is_admin(call):
        bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!")
        return

    parts = split_callback_data(call.data)
    if len(parts) < 2:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz admin isteği.")
        logger.warning(f"[admin] Invalid callback payload: {call.data}")
        return

    action = "_".join(parts[1:])
    chat_id = str(call.message.chat.id)

    bot.answer_callback_query(call.id)

    if action == "stats":
        show_stats(chat_id)

    elif action == "users":
        show_user_details(chat_id)

    elif action == "broadcast":
        set_admin_state(chat_id, "waiting_broadcast")
        bot.send_message(
            chat_id,
            "📢 <b>Duyuru</b>\n\nTüm kullanıcılara gönderilecek mesajı yazın:",
            parse_mode="HTML",
        )

    elif action == "msg":
        users = load_all_users()
        markup = types.InlineKeyboardMarkup()
        for uid, data in users.items():
            username = data.get("username", "?")
            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {uid} - {username}",
                    callback_data=f"msg_{uid}",
                )
            )
        bot.send_message(
            chat_id,
            "💬 Mesaj göndermek istediğiniz kullanıcıyı seçin:",
            reply_markup=markup,
        )

    elif action == "force":
        cb = get_check_callback()
        if cb:
            bot.send_message(chat_id, "🔄 Kontrol başlatılıyor...")
            cb()
            bot.send_message(chat_id, "✅ Kontrol tamamlandı.")
        else:
            bot.send_message(chat_id, "❌ Kontrol sistemi hazır değil.")

    elif action == "manage_courses":
        from .course_management import select_user_for_course_management

        select_user_for_course_management(chat_id)

    elif action == "manage_users":
        bot.send_message(
            chat_id,
            "👥 <b>Kullanıcı Yönetimi</b>\n\nBu özellik henüz geliştirilmiyor.",
            parse_mode="HTML",
        )

    elif action == "system_status":
        users = load_all_users()
        user_count = len(users)
        bot.send_message(
            chat_id,
            f"📊 <b>Sistem Durumu</b>\n\n👥 Kayıtlı Kullanıcı: {user_count}",
            parse_mode="HTML",
        )

    elif action == "forceoto":
        users = load_all_users()
        if not users:
            bot.send_message(chat_id, "❌ Kayıtlı kullanıcı yok.")
            return

        bot.send_message(
            chat_id,
            f"🔄 {len(users)} kullanıcı için ders taraması başlatılıyor...",
        )

        updated = 0
        failed = 0
        total_new_courses = 0

        for target_chat_id, user_data in users.items():
            username = user_data.get("username")
            password = decrypt_password(user_data.get("password", ""))

            if not username or not password:
                failed += 1
                continue

            try:
                # Create/get session (managed by SessionManager)
                session = get_user_session(target_chat_id)

                if not login_to_ninova(session, target_chat_id, username, password):
                    failed += 1
                    continue

                # Tüm dersleri çek
                courses = get_user_courses(session)
                if not courses:
                    failed += 1
                    continue

                # Mevcut verileri kontrol et
                all_grades = load_saved_grades()
                user_grades = all_grades.get(target_chat_id, {})
                current_urls = set(user_data.get("urls", []))

                # Yeni ve mevcut dersleri ayır
                already_added = []
                newly_added = []
                new_urls_list = list(current_urls)

                for course in courses:
                    course_url = course.get("url")
                    course_name = course.get("name", "Bilinmeyen Ders")

                    if not course_url:
                        continue

                    if course_url in user_grades:
                        already_added.append(course_name)
                    elif course_url in current_urls:
                        newly_added.append({"name": course_name, "url": course_url})
                    else:
                        newly_added.append({"name": course_name, "url": course_url})
                        new_urls_list.append(course_url)

                # URL'leri güncelle
                update_user_data(target_chat_id, "urls", new_urls_list)
                total_new_courses += len(newly_added)

                # Kullanıcıya bildir
                response = "📊 <b>Ders Tarama Sonucu</b>\n\n"

                if already_added:
                    response += f"✅ <b>Zaten Ekli:</b> {len(already_added)} ders\n"

                if newly_added:
                    response += "✨ <b>Yeni Eklenen Dersler:</b>\n"
                    for c in newly_added[:5]:
                        response += f"  ➕ {c['name']}\n"
                    if len(newly_added) > 5:
                        response += f"  ... ve {len(newly_added) - 5} daha\n"
                else:
                    response += "ℹ️ Yeni ders bulunamadı.\n"

                bot.send_message(target_chat_id, response, parse_mode="HTML")
                updated += 1

            except Exception:
                failed += 1
                continue

        # Admin'e özet bildir
        summary = (
            f"✅ <b>Force Otoders Tamamlandı</b>\n\n"
            f"✔️ Başarılı: {updated} kullanıcı\n"
            f"❌ Başarısız: {failed} kullanıcı\n"
            f"📚 Yeni eklenen ders: {total_new_courses}\n\n"
            f"🔄 Kontrol başlatılıyor..."
        )

        bot.send_message(chat_id, summary, parse_mode="HTML")

        # Kontrol başlat - tüm kullanıcılar için ders bilgilerini çek
        cb = get_check_callback()
        if cb:
            try:
                cb()
                bot.send_message(chat_id, "✅ Kontrol tamamlandı.", parse_mode="HTML")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Kontrol hatası: {e!s}", parse_mode="HTML")

    elif action == "logs":
        show_logs(chat_id)

    elif action == "backup":
        send_backup(chat_id)

    elif action == "optout":
        users = load_all_users()
        if not users:
            bot.send_message(chat_id, "Kayıtlı kullanıcı yok.")
            return

        markup = types.InlineKeyboardMarkup()
        for uid, data in users.items():
            username = data.get("username", "?")
            markup.add(
                types.InlineKeyboardButton(
                    f"❌ {uid} - {username}",
                    callback_data=f"opt_{uid}",
                )
            )
        bot.send_message(
            chat_id,
            "🚪 Silmek istediğiniz kullanıcıyı seçin:",
            reply_markup=markup,
        )

    elif action == "restart":
        # Tüm kullanıcılara bildir
        users_dict = load_all_users()
        for uid in users_dict:
            with contextlib.suppress(Exception):
                bot.send_message(
                    uid,
                    "🔄 Sistem güncellendi ve yeniden başlatılıyor... Lütfen bekleyiniz.",
                )

        bot.send_message(chat_id, "🔄 Bot yeniden başlatılıyor...")

        def do_restart():
            """Stop polling and restart the current process."""
            import time

            time.sleep(2)
            try:
                closed = cleanup_inactive_sessions(force=True)
                logger.info(f"[restart] Closed {closed} sessions before execv")
            except Exception as e:
                logger.exception(f"[restart] Session cleanup failed: {e}")

            with contextlib.suppress(Exception):
                bot.stop_polling()

            with contextlib.suppress(Exception):
                logging.shutdown()

            # os._exit(0) yerine execv ile yeniden başlat
            logger.warning("[restart] Replacing process with os.execv")
            os.execv(sys.executable, [sys.executable, *sys.argv])

        if not submit_background_task("admin_restart_callback", do_restart):
            bot.send_message(chat_id, "⏳ Sistem yoğun, yeniden başlatma kuyruğa alınamadı.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("msg_"))
def handle_msg_user_select(call):
    """
    Mesaj gönderilecek kullanıcı seçimini yönetir.

    Admin kullanıcı seçtikten sonra mesaj girişi bekler.

    :param call: CallbackQuery nesnesi (msg_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data)
    if len(parts) < 2:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz kullanıcı seçimi.")
        return
    target_id = parts[1]
    set_admin_state(str(call.message.chat.id), f"waiting_msg_{target_id}")

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"💬 <b>{target_id}</b> kullanıcısına gönderilecek mesajı yazın:",
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("opt_"))
def handle_optout_user(call):
    """
    Kullanıcı silme işlemini başlatır ve onay ister.

    :param call: CallbackQuery nesnesi (opt_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data)
    if len(parts) < 2:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz kullanıcı seçimi.")
        return
    target_id = parts[1]

    # Onay iste
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Evet, Sil", callback_data=f"optconf_{target_id}"),
        types.InlineKeyboardButton("❌ Vazgeç", callback_data="optcancel"),
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"⚠️ <b>{target_id}</b> kullanıcısını silmek istediğinize emin misiniz?",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("optconf_"))
def handle_optout_confirm(call):
    """
    Kullanıcı silme onayını işler.

    Kullanıcıyı users.json'dan, notları ninova_data.json'dan
    ve aktif oturumu bellekten siler.

    :param call: CallbackQuery nesnesi (optconf_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data)
    if len(parts) < 2:
        callback_parse_fail(lambda msg: bot.answer_callback_query(call.id, msg), "Geçersiz silme onayı.")
        return
    target_id = parts[1]

    # Kullanıcıyı sil
    users = load_all_users()
    if target_id in users:
        del users[target_id]
        save_all_users(users)

    # Notları sil
    grades = load_saved_grades()
    if target_id in grades:
        del grades[target_id]
        save_grades(grades)

    # Close user session
    close_user_session(target_id)

    bot.answer_callback_query(call.id, "Kullanıcı silindi!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ <b>{target_id}</b> kullanıcısı ve tüm verileri silindi.",
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "optcancel")
def handle_optout_cancel(call):
    """
    Kullanıcı silme iptalini yönetir.

    :param call: CallbackQuery nesnesi
    """
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="❌ İşlem iptal edildi.",
    )
