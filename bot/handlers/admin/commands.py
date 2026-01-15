"""
Admin komutları.
"""

import contextlib
import os
import sys
import threading

import requests
from telebot import types

from bot.instance import bot_instance as bot
from bot.instance import get_check_callback
from common.config import (
    HEADERS,
    USER_SESSIONS,
    load_all_users,
)
from common.utils import (
    decrypt_password,
    update_user_data,
)
from services.ninova import get_user_courses, login_to_ninova

from .helpers import admin_states, is_admin
from .services import (
    send_backup,
    send_broadcast,
    send_direct_message,
    show_logs,
    show_stats,
    show_user_details,
)


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

    users = load_all_users()
    stats_summary = f"👥 {len(users)} kullanıcı | 🔗 {len(USER_SESSIONS)} oturum"

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

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        admin_states[str(message.chat.id)] = "waiting_broadcast"
        bot.reply_to(message, "📢 Duyuru metnini yazın:")
        return

    broadcast_message = parts[1]
    send_broadcast(message.chat.id, broadcast_message)


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

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        # Kullanıcı listesi göster
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
        bot.reply_to(
            message,
            "💬 Mesaj göndermek istediğiniz kullanıcıyı seçin:",
            reply_markup=markup,
        )
        return

    target_id, msg_text = parts[1], parts[2]
    send_direct_message(message.chat.id, target_id, msg_text)


@bot.message_handler(commands=["restart"])
def admin_restart_cmd(message):
    """
    Botu yeniden başlatır.

    Tüm kullanıcılara bildirim gönderir ve sistemi yeniden başlatır.

    :param message: Admin'den gelen /restart komutu
    """
    if not is_admin(message):
        return

    # Tüm kullanıcılara bildir
    users_dict = load_all_users()
    for uid in users_dict:
        with contextlib.suppress(Exception):
            bot.send_message(
                uid,
                "🔄 Sistem güncellendi ve yeniden başlatılıyor... Lütfen bekleyiniz.",
            )

    bot.reply_to(message, "🔄 Bot yeniden başlatılıyor...")

    # Bot polling'i durdur ve çık
    def do_restart():
        """Stop polling and restart the current process."""
        import time

        time.sleep(2)  # Mesajların gitmesini bekle
        with contextlib.suppress(Exception):
            bot.stop_polling()
        # os._exit(0) yerine execv ile yeniden başlat
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=do_restart, daemon=True).start()


def admin_stats_cmd(message):
    """
    Detaylı sistem istatistiklerini gösterir.

    :param message: Admin'den gelen /stats komutu
    """
    if not is_admin(message):
        return
    show_stats(message.chat.id)


def admin_backup_cmd(message):
    """
    Veritabanı yedeği gönderir.

    :param message: Admin'den gelen /backup komutu
    """
    if not is_admin(message):
        return
    send_backup(message.chat.id)


def admin_detail_cmd(message):
    """
    Tüm kullanıcıların detaylarını gösterir.

    :param message: Admin'den gelen /detay komutu
    """
    if not is_admin(message):
        return
    show_user_details(message.chat.id)


def admin_optout_cmd(message):
    """
    Kullanıcı silme menüsü açar.

    Admin'in seçtiği kullanıcıyı ve tüm verilerini sistemden siler.

    :param message: Admin'den gelen /optout komutu
    """
    if not is_admin(message):
        return

    users = load_all_users()
    if not users:
        bot.reply_to(message, "Kayıtlı kullanıcı yok.")
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
    if not is_admin(message):
        return
    show_logs(message.chat.id)


def admin_force_check_cmd(message):
    """
    Tüm kullanıcılar için manuel kontrol başlatır.

    Zamanlanmış kontrol beklemeden hemen tüm kullanıcılar için
    Ninova tarama ve güncelleme kontrolü yapar.

    :param message: Admin'den gelen /force_check komutu
    """
    if not is_admin(message):
        return

    cb = get_check_callback()
    if cb:
        bot.reply_to(message, "🔄 Tüm kullanıcılar için kontrol başlatılıyor...")
        cb()
        bot.send_message(message.chat.id, "✅ Kontrol tamamlandı.")
    else:
        bot.reply_to(message, "❌ Kontrol sistemi hazır değil.")


def admin_force_otoders_cmd(message):
    """
    Tüm kullanıcıların ders listesini zorla günceller.

    Her kullanıcı için Ninova'ya bağlanıp tüm dersleri yeniden çeker
    ve mevcut ders listesini günceller. Eski dersler temizlenir.

    :param message: Admin'den gelen /force_otoders komutu
    """
    if not is_admin(message):
        return

    users = load_all_users()
    if not users:
        bot.reply_to(message, "❌ Kayıtlı kullanıcı yok.")
        return

    bot.reply_to(
        message,
        f"🔄 {len(users)} kullanıcı için ders taraması başlatılıyor...",
    )

    updated = 0
    failed = 0

    for chat_id, user_data in users.items():
        username = user_data.get("username")
        password = decrypt_password(user_data.get("password", ""))

        if not username or not password:
            failed += 1
            continue

        try:
            # Yeni oturum oluştur (eski oturumu sıfırla)
            USER_SESSIONS[chat_id] = requests.Session()
            USER_SESSIONS[chat_id].headers.update(HEADERS)

            session = USER_SESSIONS[chat_id]

            if not login_to_ninova(session, chat_id, username, password):
                failed += 1
                continue

            # Tüm dersleri çek
            courses = get_user_courses(session)
            if not courses:
                failed += 1
                continue

            # Eski dersleri temizle ve yenilerini ekle
            new_urls = [course["url"] for course in courses]
            update_user_data(chat_id, "urls", new_urls)

            # Kullanıcıya bildir
            course_list = "\n".join([f"📚 {c['name']}" for c in courses[:10]])
            if len(courses) > 10:
                course_list += f"\n... ve {len(courses) - 10} daha"

            bot.send_message(
                chat_id,
                f"✅ <b>Ders Listesi Güncellendi</b>\n\n{course_list}\n\n<b>Toplam: {len(courses)} ders</b>",
                parse_mode="HTML",
            )

            updated += 1

        except Exception:
            failed += 1
            continue

    # Admin'e özet bildir
    summary = (
        f"✅ <b>Force Otoders Tamamlandı</b>\n\n"
        f"✔️ Başarılı: {updated} kullanıcı\n"
        f"❌ Başarısız: {failed} kullanıcı\n\n"
        f"🔄 Kontrol başlatılıyor..."
    )

    bot.send_message(message.chat.id, summary, parse_mode="HTML")

    # Kontrol başlat
    cb = get_check_callback()
    if cb:
        with contextlib.suppress(Exception):
            cb()
