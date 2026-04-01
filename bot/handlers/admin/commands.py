"""
Admin komutları.
"""

import logging
import os
import sys

from telebot import types

from bot.instance import bot_instance as bot
from bot.instance import get_check_callback
from common.background_tasks import submit_background_task
from common.config import (
    cleanup_inactive_sessions,
    get_active_user_sessions,
    get_user_session,
)
from common.utils import (
    decrypt_password,
    save_grades,
    update_user_data,
)
from services.ninova import get_class_info, get_user_courses, login_to_ninova

from .data_helpers import load_admin_grades, load_admin_users
from .helpers import is_admin, log_admin_action, new_admin_request_id, set_admin_state
from .services import (
    send_backup,
    send_broadcast,
    send_direct_message,
    show_logs,
    show_stats,
    show_user_details,
)

logger = logging.getLogger("ninova")


@bot.message_handler(func=lambda message: message.text == "👑 Admin")
def admin_panel(message):
    """
    Admin panelini açar ve tüm admin fonksiyonlarına erişim sağlar.

    Panel üzerinden erişilebilir özellikler:
    - İstatistikler
    - Kullanıcı listesi
    - Duyuru gönderme
    - Direkt mesaj gönderme
    - Force check (manuel kontrol)
    - Loglar
    - Backup
    - Kullanıcı silme
    - Ders yönetimi
    - Sistem yeniden başlatma

    :param message: Admin'den gelen /admin komutu
    """
    if not is_admin(message):
        bot.reply_to(message, "⛔ Bu paneli görüntüleme yetkiniz yok.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats"),
        types.InlineKeyboardButton("👥 Kullanıcılar", callback_data="adm_users"),
        types.InlineKeyboardButton("📢 Duyuru Yap", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("💬 Mesaj Gönder", callback_data="adm_msg"),
        types.InlineKeyboardButton("🔄 Force Check", callback_data="adm_force"),
        types.InlineKeyboardButton("📚 Force Otoders", callback_data="adm_forceoto"),
        types.InlineKeyboardButton("🚪 Kullanıcı Sil", callback_data="adm_optout"),
        types.InlineKeyboardButton("📚 User Ders Yönetimi", callback_data="adm_manage_courses"),
        types.InlineKeyboardButton("📂 Loglar", callback_data="adm_logs"),
        types.InlineKeyboardButton("💾 Backup", callback_data="adm_backup"),
        types.InlineKeyboardButton("🔄 Restart", callback_data="adm_restart"),
    )

    request_id = new_admin_request_id("cmd")
    users = load_admin_users()
    log_admin_action(str(message.chat.id), "admin_panel", status="opened", request_id=request_id)
    stats_summary = f"👥 {len(users)} kullanıcı | 🔗 {len(get_active_user_sessions())} oturum"

    bot.reply_to(
        message,
        f"🛠 <b>Admin Paneli</b>\n\n{stats_summary}",
        reply_markup=markup,
        parse_mode="HTML",
    )


def admin_broadcast_cmd(message):
    """
    Tüm kullanıcılara duyuru gönderir.

    Kullanım:
    - /duyuru <mesaj> : Direkt duyuru gönderir
    - /duyuru : Mesaj girişi bekler

    :param message: Admin'den gelen /duyuru komutu
    """
    if not is_admin(message):
        return

    request_id = new_admin_request_id("cmd")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        set_admin_state(str(message.chat.id), "waiting_broadcast")
        log_admin_action(
            str(message.chat.id), "broadcast", status="awaiting_text", request_id=request_id
        )
        bot.reply_to(message, "📢 Duyuru metnini yazın:")
        return

    broadcast_message = parts[1]
    log_admin_action(str(message.chat.id), "broadcast", status="started", request_id=request_id)
    send_broadcast(message.chat.id, broadcast_message, request_id=request_id)


def admin_msg_cmd(message):
    """
    Belirli bir kullanıcıya mesaj gönderir.

    Kullanım:
    - /msg <chat_id> <mesaj> : Direkt mesaj gönderir
    - /msg : Kullanıcı seçim menüsünü gösterir

    :param message: Admin'den gelen /msg komutu
    """
    if not is_admin(message):
        return

    request_id = new_admin_request_id("cmd")
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        # Kullanıcı listesi göster
        users = load_admin_users()
        log_admin_action(
            str(message.chat.id),
            "direct_message",
            status="target_selection",
            request_id=request_id,
        )
        markup = types.InlineKeyboardMarkup()
        for uid, data in users.items():
            username = data.get("username", "?")
            markup.add(
                types.InlineKeyboardButton(
                    f"👤 {uid} - {username}",
                    callback_data=f"msg_{uid}",
                )
            )
        bot.reply_to(
            message,
            "💬 Mesaj göndermek istediğiniz kullanıcıyı seçin:",
            reply_markup=markup,
        )
        return

    target_id, msg_text = parts[1], parts[2]
    log_admin_action(
        str(message.chat.id),
        "direct_message",
        status="started",
        request_id=request_id,
        target_id=target_id,
    )
    send_direct_message(message.chat.id, target_id, msg_text, request_id=request_id)


@bot.message_handler(commands=["restart"])
def admin_restart_cmd(message):
    """
    Botu yeniden başlatır.

    Sistemi yeniden başlatır.

    :param message: Admin'den gelen /restart komutu
    """
    if not is_admin(message):
        return

    request_id = new_admin_request_id("cmd")
    log_admin_action(str(message.chat.id), "restart", status="started", request_id=request_id)

    bot.reply_to(message, "🔄 Bot yeniden başlatılıyor...")

    # Bot polling'i durdur ve çık
    def do_restart():
        """Stop polling and restart the current process."""
        import time

        time.sleep(2)  # Mesajların gitmesini bekle
        try:
            closed = cleanup_inactive_sessions(force=True)
            logger.info(f"[restart] Closed {closed} sessions before execv")
        except Exception as e:
            logger.exception(f"[restart] Session cleanup failed: {e}")

        try:
            bot.stop_polling()
        except Exception as e:
            logger.debug(f"[restart] stop_polling failed: {e}")

        try:
            logging.shutdown()
        except Exception as e:
            logger.debug(f"[restart] logging shutdown failed: {e}")

        # os._exit(0) yerine execv ile yeniden başlat
        logger.warning("[restart] Replacing process with os.execv")
        os.execv(sys.executable, [sys.executable, *sys.argv])

    if not submit_background_task("admin_restart_cmd", do_restart):
        bot.reply_to(message, "⏳ Sistem yoğun, yeniden başlatma kuyruğa alınamadı.")
        log_admin_action(
            str(message.chat.id),
            "restart",
            status="queue_full",
            request_id=request_id,
            level="warning",
        )


def admin_stats_cmd(message):
    """
    Detaylı sistem istatistiklerini gösterir.

    :param message: Admin'den gelen /stats komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return
    log_admin_action(str(message.chat.id), "show_stats", status="requested", request_id=request_id)
    show_stats(message.chat.id)


def admin_backup_cmd(message):
    """
    Veritabanı yedeği gönderir.

    :param message: Admin'den gelen /backup komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return
    log_admin_action(str(message.chat.id), "backup", status="requested", request_id=request_id)
    send_backup(message.chat.id)


def admin_detail_cmd(message):
    """
    Tüm kullanıcıların detaylarını gösterir.

    :param message: Admin'den gelen /detay komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return
    log_admin_action(str(message.chat.id), "show_users", status="requested", request_id=request_id)
    show_user_details(message.chat.id)


def admin_optout_cmd(message):
    """
    Kullanıcı silme menüsü açar.

    Admin'in seçtiği kullanıcıyı ve tüm verilerini sistemden siler.

    :param message: Admin'den gelen /optout komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return

    users = load_admin_users()
    if not users:
        bot.reply_to(message, "Kayıtlı kullanıcı yok.")
        log_admin_action(
            str(message.chat.id),
            "optout",
            status="no_users",
            request_id=request_id,
            level="warning",
        )
        return

    log_admin_action(
        str(message.chat.id), "optout", status="target_selection", request_id=request_id
    )

    markup = types.InlineKeyboardMarkup()
    for uid, data in users.items():
        username = data.get("username", "?")
        markup.add(
            types.InlineKeyboardButton(
                f"❌ {uid} - {username}",
                callback_data=f"opt_{uid}",
            )
        )

    bot.reply_to(
        message,
        "🚪 Silmek istediğiniz kullanıcıyı seçin:",
        reply_markup=markup,
    )


def admin_logs_cmd(message):
    """
    Son logları gösterir.

    :param message: Admin'den gelen /logs komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return
    log_admin_action(str(message.chat.id), "show_logs", status="requested", request_id=request_id)
    show_logs(message.chat.id)


def admin_force_check_cmd(message):
    """
    Tüm kullanıcılar için manuel kontrol başlatır.

    Zamanlanmış kontrol beklemeden hemen tüm kullanıcılar için
    Ninova tarama ve güncelleme kontrolü yapar.

    :param message: Admin'den gelen /force_check komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return

    cb = get_check_callback()
    if cb:
        log_admin_action(
            str(message.chat.id), "force_check", status="started", request_id=request_id
        )
        bot.reply_to(message, "🔄 Tüm kullanıcılar için kontrol başlatılıyor...")
        cb()
        bot.send_message(message.chat.id, "✅ Kontrol tamamlandı.")
        log_admin_action(
            str(message.chat.id), "force_check", status="completed", request_id=request_id
        )
    else:
        bot.reply_to(message, "❌ Kontrol sistemi hazır değil.")
        log_admin_action(
            str(message.chat.id),
            "force_check",
            status="not_ready",
            request_id=request_id,
            level="warning",
        )


def admin_force_otoders_cmd(message):
    """
    Tüm kullanıcıların ders listesini akıllıca günceller.

    1. ninova_data.json içindeki yetim verileri (users.json'da olmayan) temizler.
    2. Kullanıcıların derslerini tarar ve sadece aktif (tarihi geçmemiş) olanları ekler.

    :param message: Admin'den gelen /force_otoders komutu
    """
    request_id = new_admin_request_id("cmd")
    if not is_admin(message):
        return

    users = load_admin_users()
    if not users:
        bot.reply_to(message, "❌ Kayıtlı kullanıcı yok.")
        log_admin_action(
            str(message.chat.id),
            "force_otoders",
            status="no_users",
            request_id=request_id,
            level="warning",
        )
        return

    log_admin_action(
        str(message.chat.id),
        "force_otoders",
        status="started",
        request_id=request_id,
        details=f"users={len(users)}",
    )

    bot.reply_to(
        message,
        f"🔄 {len(users)} kullanıcı için VERİ TEMİZLİĞİ ve DERS TARAMASI başlatılıyor...\nBu işlem uzun sürebilir.",
    )

    # --- 1. CLEANUP ORPHANED DATA ---
    try:
        all_grades = load_admin_grades()
        cleaned_courses_count = 0
        cleaned_users_count = 0

        # Remove users from grades if they don't exist in users.json
        users_to_remove = [uid for uid in all_grades if uid not in users]
        for uid in users_to_remove:
            del all_grades[uid]
            cleaned_users_count += 1

        # Remove courses from grades if they are not in user's url list
        for chat_id, user_grades_data in list(all_grades.items()):
            if chat_id not in users:
                continue

            user_urls = set(users[chat_id].get("urls", []))
            courses_to_remove = [url for url in user_grades_data if url not in user_urls]

            for url in courses_to_remove:
                del user_grades_data[url]
                cleaned_courses_count += 1

        if cleaned_users_count > 0 or cleaned_courses_count > 0:
            save_grades(all_grades)
            bot.send_message(
                message.chat.id,
                f"🧹 <b>Veri Temizliği Tamamlandı</b>\n"
                f"- Silinen Eski Kullanıcı Verisi: {cleaned_users_count}\n"
                f"- Silinen Yetim Ders Verisi: {cleaned_courses_count}",
                parse_mode="HTML",
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Veri temizliği sırasında hata: {e!s}")

    # --- 2. SMART AUTO ADD ---
    from datetime import datetime

    updated_users = 0
    failed_users = 0
    total_added_courses = 0

    for chat_id, user_data in users.items():
        username = user_data.get("username")
        password = decrypt_password(user_data.get("password", ""))

        if not username or not password:
            failed_users += 1
            from main import _record_user_error

            _record_user_error(
                chat_id, "MISSING_CREDENTIALS", "Eksik kullanıcı adı/şifre", username
            )
            continue

        try:
            # Yeni oturum oluştur (SessionManager tarafından yönetilir)
            session = get_user_session(chat_id)

            if not login_to_ninova(session, chat_id, username, password):
                failed_users += 1
                from main import _record_user_error

                _record_user_error(
                    chat_id,
                    "LOGIN_FAILED",
                    "Admin force otoders sırasında giriş başarısız",
                    username,
                )
                continue

            # Tüm dersleri çek
            courses = get_user_courses(session)
            if not courses:
                continue  # Ders yoksa işlem yapma

            current_urls = set(user_data.get("urls", []))
            new_urls_list = list(current_urls)
            added_for_this_user = 0

            now = datetime.now()

            for course in courses:
                url = course["url"]

                if url in current_urls:
                    continue

                # Yeni ders, tarih kontrolü yap
                class_info = get_class_info(session, url)
                end_date = class_info.get("end_date")

                is_expired = False
                if end_date and end_date < now:
                    is_expired = True

                if not is_expired:
                    new_urls_list.append(url)
                    added_for_this_user += 1

            # Eğer değişiklik varsa kaydet
            if added_for_this_user > 0:
                update_user_data(chat_id, "urls", new_urls_list)
                total_added_courses += added_for_this_user

                bot.send_message(
                    chat_id,
                    f"🤖 <b>Admin Otomatik Güncelleme</b>\n"
                    f"{added_for_this_user} yeni aktif ders listenize eklendi.",
                    parse_mode="HTML",
                )
                updated_users += 1

        except Exception as e:
            logger.exception(f"[admin] force_otoders failed for user {chat_id}: {e}")
            failed_users += 1
            from main import _record_user_error

            _record_user_error(chat_id, "FORCE_OTODERS_EXCEPTION", str(e), username)
            continue

    # Admin'e özet bildir
    summary = (
        f"✅ <b>Force Otoders (Akıllı Mod) Tamamlandı</b>\n\n"
        f"✔️ Güncellenen Kullanıcı: {updated_users}\n"
        f"📚 Toplam Eklenen Yeni Ders: {total_added_courses}\n"
        f"❌ Hata/Eksik Bilgi: {failed_users} kullanıcı\n\n"
        f"🔄 Kontrol başlatılıyor..."
    )

    bot.send_message(message.chat.id, summary, parse_mode="HTML")
    log_admin_action(
        str(message.chat.id),
        "force_otoders",
        status="completed",
        request_id=request_id,
        details=f"updated={updated_users};failed={failed_users};new_courses={total_added_courses}",
    )

    # Kontrol başlat
    cb = get_check_callback()
    if cb:
        try:
            cb()
        except Exception as e:
            logger.exception(f"[force_otoders] Post-sync full check failed: {e}")
