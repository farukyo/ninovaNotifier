"""
Admin komutları ve callback'leri.
README'deki tüm admin özellikleri burada tanımlıdır.
"""

import os
import requests
from datetime import datetime
from telebot import types
from bot.core import bot_instance as bot, get_check_callback, START_TIME
from core.config import (
    load_all_users,
    save_all_users,
    USER_SESSIONS,
    DATA_FILE,
    USERS_FILE,
    LOGS_DIR,
    HEADERS,
)
from core.utils import (
    load_saved_grades,
    save_grades,
    update_user_data,
    decrypt_password,
)
from ninova import login_to_ninova, get_user_courses

# Admin ID - ENV'den alınır
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")

# Admin state'leri (duyuru/msg için)
admin_states = {}


def is_admin(message_or_call):
    """Admin kontrolü yapar."""
    if hasattr(message_or_call, "chat"):
        return str(message_or_call.chat.id) == ADMIN_ID
    elif hasattr(message_or_call, "message"):
        return str(message_or_call.message.chat.id) == ADMIN_ID
    return False


def get_uptime():
    """Bot çalışma süresini hesaplar."""
    delta = datetime.now() - START_TIME
    days, remainder = divmod(int(delta.total_seconds()), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}g {hours}s {minutes}dk"
    return f"{hours}s {minutes}dk {seconds}sn"


# ========== ADMIN KOMUTLARI ==========


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    """Admin panelini açar."""
    if not is_admin(message):
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats"),
        types.InlineKeyboardButton("👥 Kullanıcılar", callback_data="adm_users"),
        types.InlineKeyboardButton("📢 Duyuru Yap", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("💬 Mesaj Gönder", callback_data="adm_msg"),
        types.InlineKeyboardButton("🔄 Force Check", callback_data="adm_force"),
        types.InlineKeyboardButton("📂 Loglar", callback_data="adm_logs"),
        types.InlineKeyboardButton("💾 Backup", callback_data="adm_backup"),
        types.InlineKeyboardButton("🚪 Kullanıcı Sil", callback_data="adm_optout"),
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Restart", callback_data="adm_restart"),
        types.InlineKeyboardButton("📚 Force Otoders", callback_data="adm_forceoto"),
    )

    users = load_all_users()
    stats_summary = f"👥 {len(users)} kullanıcı | 🔗 {len(USER_SESSIONS)} oturum"

    bot.reply_to(
        message,
        f"🛠 <b>Admin Paneli</b>\n\n{stats_summary}",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(commands=["duyuru"])
def admin_broadcast_cmd(message):
    """Tüm kullanıcılara duyuru gönderir."""
    if not is_admin(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        admin_states[str(message.chat.id)] = "waiting_broadcast"
        bot.reply_to(message, "📢 Duyuru metnini yazın:")
        return

    broadcast_message = parts[1]
    send_broadcast(message.chat.id, broadcast_message)


@bot.message_handler(commands=["msg"])
def admin_msg_cmd(message):
    """Belirli bir kullanıcıya mesaj gönderir."""
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
    """Botu yeniden başlatır."""
    if not is_admin(message):
        return

    import sys
    import threading

    # Tüm kullanıcılara bildir
    users_dict = load_all_users()
    for uid in users_dict:
        try:
            bot.send_message(
                uid,
                "🔄 Sistem güncellendi ve yeniden başlatılıyor... Lütfen bekleyiniz.",
            )
        except Exception:
            pass

    bot.reply_to(message, "🔄 Bot yeniden başlatılıyor...")

    # Bot polling'i durdur ve çık
    def do_restart():
        import time

        time.sleep(2)  # Mesajların gitmesini bekle
        try:
            bot.stop_polling()
        except Exception:
            pass
        # os._exit(0) yerine execv ile yeniden başlat
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=do_restart, daemon=True).start()


@bot.message_handler(commands=["stats"])
def admin_stats_cmd(message):
    """Detaylı istatistikleri gösterir."""
    if not is_admin(message):
        return
    show_stats(message.chat.id)


@bot.message_handler(commands=["backup"])
def admin_backup_cmd(message):
    """Veritabanı yedeği gönderir."""
    if not is_admin(message):
        return
    send_backup(message.chat.id)


@bot.message_handler(commands=["detay"])
def admin_detail_cmd(message):
    """Tüm kullanıcıların detaylarını gösterir."""
    if not is_admin(message):
        return
    show_user_details(message.chat.id)


@bot.message_handler(commands=["optout"])
def admin_optout_cmd(message):
    """Kullanıcı silme menüsü açar."""
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


@bot.message_handler(commands=["logs"])
def admin_logs_cmd(message):
    """Son logları gösterir."""
    if not is_admin(message):
        return
    show_logs(message.chat.id)


@bot.message_handler(commands=["force_check"])
def admin_force_check_cmd(message):
    """Tüm kullanıcılar için kontrol başlatır."""
    if not is_admin(message):
        return

    cb = get_check_callback()
    if cb:
        bot.reply_to(message, "🔄 Tüm kullanıcılar için kontrol başlatılıyor...")
        cb()
        bot.send_message(message.chat.id, "✅ Kontrol tamamlandı.")
    else:
        bot.reply_to(message, "❌ Kontrol sistemi hazır değil.")


@bot.message_handler(commands=["force_otoders"])
def admin_force_otoders_cmd(message):
    """Tüm kullanıcıların ders listesini kuvvetle günceller (yeniden başlatan version)."""
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
        try:
            cb()
        except Exception:
            pass


# ========== ADMIN CALLBACK'LERİ ==========


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def handle_admin_callbacks(call):
    """Admin panel callback'lerini yönetir."""
    if not is_admin(call):
        bot.answer_callback_query(call.id, "⛔ Yetkiniz yok!")
        return

    action = call.data.split("_")[1]
    chat_id = str(call.message.chat.id)

    bot.answer_callback_query(call.id)

    if action == "stats":
        show_stats(chat_id)

    elif action == "users":
        show_user_details(chat_id)

    elif action == "broadcast":
        admin_states[chat_id] = "waiting_broadcast"
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

        for target_chat_id, user_data in users.items():
            username = user_data.get("username")
            password = decrypt_password(user_data.get("password", ""))

            if not username or not password:
                failed += 1
                continue

            try:
                # Yeni oturum oluştur (eski oturumu sıfırla)
                USER_SESSIONS[target_chat_id] = requests.Session()
                USER_SESSIONS[target_chat_id].headers.update(HEADERS)

                session = USER_SESSIONS[target_chat_id]

                if not login_to_ninova(session, target_chat_id, username, password):
                    failed += 1
                    continue

                # Tüm dersleri çek
                courses = get_user_courses(session)
                if not courses:
                    failed += 1
                    continue

                # Eski dersleri temizle ve yenilerini ekle
                new_urls = [course["url"] for course in courses]
                update_user_data(target_chat_id, "urls", new_urls)

                # Kullanıcıya bildir
                course_list = "\n".join([f"📚 {c['name']}" for c in courses[:10]])
                if len(courses) > 10:
                    course_list += f"\n... ve {len(courses) - 10} daha"

                bot.send_message(
                    target_chat_id,
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

        bot.send_message(chat_id, summary, parse_mode="HTML")

        # Kontrol başlat
        cb = get_check_callback()
        if cb:
            try:
                cb()
            except Exception:
                pass

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
        import sys
        import threading

        # Tüm kullanıcılara bildir
        users_dict = load_all_users()
        for uid in users_dict:
            try:
                bot.send_message(
                    uid,
                    "🔄 Sistem güncellendi ve yeniden başlatılıyor... Lütfen bekleyiniz.",
                )
            except Exception:
                pass

        bot.send_message(chat_id, "🔄 Bot yeniden başlatılıyor...")

        def do_restart():
            import time

            time.sleep(2)
            try:
                bot.stop_polling()
            except Exception:
                pass
            # os._exit(0) yerine execv ile yeniden başlat
            os.execv(sys.executable, [sys.executable] + sys.argv)

        threading.Thread(target=do_restart, daemon=True).start()


@bot.callback_query_handler(func=lambda call: call.data.startswith("msg_"))
def handle_msg_user_select(call):
    """Mesaj gönderilecek kullanıcı seçimi."""
    if not is_admin(call):
        return

    target_id = call.data.split("_")[1]
    admin_states[str(call.message.chat.id)] = f"waiting_msg_{target_id}"

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"💬 <b>{target_id}</b> kullanıcısına gönderilecek mesajı yazın:",
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("opt_"))
def handle_optout_user(call):
    """Kullanıcı silme işlemi."""
    if not is_admin(call):
        return

    target_id = call.data.split("_")[1]

    # Onay iste
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ Evet, Sil", callback_data=f"optconf_{target_id}"
        ),
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
    """Kullanıcı silme onayı."""
    if not is_admin(call):
        return

    target_id = call.data.split("_")[1]

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

    # Oturumu sil
    if target_id in USER_SESSIONS:
        try:
            USER_SESSIONS[target_id].close()
            del USER_SESSIONS[target_id]
        except Exception:
            pass

    bot.answer_callback_query(call.id, "Kullanıcı silindi!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ <b>{target_id}</b> kullanıcısı ve tüm verileri silindi.",
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "optcancel")
def handle_optout_cancel(call):
    """Kullanıcı silme iptali."""
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="❌ İşlem iptal edildi.",
    )


# ========== YARDIMCI FONKSİYONLAR ==========


def show_stats(chat_id):
    """Detaylı istatistikleri gösterir."""
    users = load_all_users()

    total_users = len(users)
    total_courses = sum(len(u.get("urls", [])) for u in users.values())
    active_sessions = len(USER_SESSIONS)

    # Dosya boyutları
    users_size = os.path.getsize(USERS_FILE) / 1024 if os.path.exists(USERS_FILE) else 0
    data_size = os.path.getsize(DATA_FILE) / 1024 if os.path.exists(DATA_FILE) else 0
    log_file_path = os.path.join(LOGS_DIR, "app.log")
    log_size = (
        os.path.getsize(log_file_path) / 1024 if os.path.exists(log_file_path) else 0
    )

    stats = (
        "📊 <b>Sistem İstatistikleri</b>\n\n"
        f"👥 <b>Kullanıcılar:</b> {total_users}\n"
        f"📚 <b>Toplam Ders:</b> {total_courses}\n"
        f"🔗 <b>Aktif Oturum:</b> {active_sessions}\n"
        f"⏱ <b>Uptime:</b> {get_uptime()}\n\n"
        f"💾 <b>Dosya Boyutları:</b>\n"
        f"├ users.json: {users_size:.1f} KB\n"
        f"├ ninova_data.json: {data_size:.1f} KB\n"
        f"└ app.log: {log_size:.1f} KB"
    )

    bot.send_message(chat_id, stats, parse_mode="HTML")


def show_user_details(chat_id):
    """Tüm kullanıcıların detaylarını gösterir."""
    users = load_all_users()

    if not users:
        bot.send_message(chat_id, "Kayıtlı kullanıcı yok.")
        return

    response = "👥 <b>Kullanıcı Detayları</b>\n\n"
    for uid, data in users.items():
        username = data.get("username", "?")
        url_count = len(data.get("urls", []))
        has_session = "✅" if uid in USER_SESSIONS else "❌"
        response += f"🆔 <code>{uid}</code>\n"
        response += f"├ 👤 {username}\n"
        response += f"├ 📚 {url_count} ders\n"
        response += f"└ 🔗 Oturum: {has_session}\n\n"

    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            bot.send_message(chat_id, response[i : i + 4000], parse_mode="HTML")
    else:
        bot.send_message(chat_id, response, parse_mode="HTML")


def show_logs(chat_id, lines=30):
    """Son logları gösterir veya dosya olarak gönderir."""
    log_file = os.path.join(LOGS_DIR, "app.log")

    if not os.path.exists(log_file):
        bot.send_message(chat_id, "📂 Log dosyası bulunamadı.")
        return

    file_size = os.path.getsize(log_file)

    # Büyük dosyayı doğrudan gönder
    if file_size > 50 * 1024:  # 50KB'dan büyükse
        with open(log_file, "rb") as f:
            bot.send_document(chat_id, f, caption="📋 app.log")
        return

    # Küçük dosyanın son satırlarını göster
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            log_text = "".join(last_lines)

        if len(log_text) > 4000:
            log_text = log_text[-4000:]

        bot.send_message(
            chat_id,
            f"📋 <b>Son {len(last_lines)} Log Kaydı</b>\n\n<pre>{log_text}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Log okuma hatası: {e}")


def send_backup(chat_id):
    """Veritabanı dosyalarını yedek olarak gönderir."""
    files_sent = 0

    for filename in [USERS_FILE, DATA_FILE]:
        if os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    bot.send_document(
                        chat_id,
                        f,
                        caption=f"💾 Yedek: {filename}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    )
                files_sent += 1
            except Exception as e:
                bot.send_message(chat_id, f"❌ {filename} gönderilemedi: {e}")

    if files_sent == 0:
        bot.send_message(chat_id, "❌ Yedeklenecek dosya bulunamadı.")
    else:
        bot.send_message(chat_id, f"✅ {files_sent} dosya yedeklendi.")


def send_broadcast(admin_chat_id, message_text):
    """Tüm kullanıcılara duyuru gönderir."""
    users = load_all_users()

    if not users:
        bot.send_message(admin_chat_id, "❌ Kayıtlı kullanıcı yok.")
        return

    success_count = 0
    fail_count = 0

    broadcast_msg = f"📢 <b>Sistem Duyurusu</b>\n\n{message_text}"

    for uid in users.keys():
        try:
            bot.send_message(uid, broadcast_msg, parse_mode="HTML")
            success_count += 1
        except Exception:
            fail_count += 1

    bot.send_message(
        admin_chat_id,
        f"📢 <b>Duyuru Gönderildi</b>\n\n"
        f"✅ Başarılı: {success_count}\n"
        f"❌ Başarısız: {fail_count}",
        parse_mode="HTML",
    )


def send_direct_message(admin_chat_id, target_id, message_text):
    """Belirli bir kullanıcıya mesaj gönderir."""
    try:
        bot.send_message(
            target_id,
            f"💬 <b>Admin Mesajı</b>\n\n{message_text}",
            parse_mode="HTML",
        )
        bot.send_message(
            admin_chat_id,
            f"✅ Mesaj <b>{target_id}</b> kullanıcısına gönderildi.",
            parse_mode="HTML",
        )
    except Exception as e:
        bot.send_message(admin_chat_id, f"❌ Mesaj gönderilemedi: {e}")


# ========== ADMIN STATE HANDLER (Duyuru/Mesaj için) ==========


@bot.message_handler(func=lambda m: str(m.chat.id) in admin_states)
def handle_admin_text(message):
    """Admin duyuru ve mesaj girişlerini yakalar."""
    chat_id = str(message.chat.id)
    if not is_admin(message):
        return

    state = admin_states.get(chat_id)
    if not state:
        return

    # State'i temizle
    del admin_states[chat_id]

    if state == "waiting_broadcast":
        send_broadcast(chat_id, message.text)
    elif state.startswith("waiting_msg_"):
        target_id = state.replace("waiting_msg_", "")
        send_direct_message(chat_id, target_id, message.text)
