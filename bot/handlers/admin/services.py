"""
Admin yardımcı fonksiyonları.
"""

import os
from datetime import datetime
from bot.instance import bot_instance as bot
from common.config import (
    load_all_users,
    USER_SESSIONS,
    DATA_FILE,
    USERS_FILE,
    LOGS_DIR,
)
from .helpers import is_admin, admin_states, get_uptime


def show_stats(chat_id):
    """
    Admin'e detaylı sistem istatistiklerini gösterir.

    Kullanıcı sayısı, ders sayısı, aktif oturum sayısı,
    uptime ve dosya boyutları gibi bilgileri içerir.

    :param chat_id: Admin'in chat ID'si
    """
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
    """
    Tüm kullanıcıların detaylı bilgilerini admin'e gösterir.

    Her kullanıcı için: chat ID, kullanıcı adı, ders sayısı ve
    aktif oturum durumu gösterilir.

    :param chat_id: Admin'in chat ID'si
    """
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
    """
    Son logları admin'e gösterir veya dosya olarak gönderir.

    Log dosyası 50KB'ın üzerindeyse tüm dosyayı gönderir,
    değilse son N satırı mesaj olarak gösterir.

    :param chat_id: Admin'in chat ID'si
    :param lines: Gösterilecek maksimum satır sayısı (varsayılan: 30)
    """
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
    """
    Veritabanı dosyalarını (users.json, ninova_data.json) yedek olarak admin'e gönderir.

    :param chat_id: Admin'in chat ID'si
    """
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
    """
    Tüm kullanıcılara duyuru mesajı gönderir.

    Başarılı ve başarısız gönderim sayılarını admin'e bildirir.

    :param admin_chat_id: Admin'in chat ID'si
    :param message_text: Gönderilecek duyuru mesajı
    """
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
    """
    Belirli bir kullanıcıya admin mesajı gönderir.

    :param admin_chat_id: Admin'in chat ID'si
    :param target_id: Hedef kullanıcının chat ID'si
    :param message_text: Gönderilecek mesaj
    """
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


@bot.message_handler(func=lambda m: str(m.chat.id) in admin_states)
def handle_admin_text(message):
    """
    Admin duyuru ve mesaj girişlerini yakalar.

    Admin panel üzerinden duyuru veya özel mesaj gönderme
    işlemlerinde kullanıcıdan metin girişi bekler.

    :param message: Admin'den gelen mesaj
    """
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
