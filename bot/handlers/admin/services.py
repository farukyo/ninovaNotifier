"""
Admin yardımcı fonksiyonları.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from bot.instance import bot_instance as bot
from bot.keyboards import build_main_keyboard
from common.config import (
    DATA_FILE,
    LOGS_DIR,
    USERS_FILE,
    get_active_user_sessions,
    has_user_session,
)

from .data_helpers import load_admin_users
from .helpers import (
    get_admin_state,
    get_uptime,
    has_admin_state,
    is_admin,
    log_admin_action,
    pop_admin_state,
)

logger = logging.getLogger("ninova")


def _collect_runtime_metrics() -> dict[str, str]:
    """Collect runtime metrics without background timers."""
    metrics = {
        "cpu_percent": "N/A",
        "ram_percent": "N/A",
        "ram_used_mb": "N/A",
        "disk_percent": "N/A",
        "disk_free_gb": "N/A",
    }

    try:
        usage = shutil.disk_usage(Path())
        metrics["disk_percent"] = f"{(usage.used / usage.total) * 100:.1f}%"
        metrics["disk_free_gb"] = f"{usage.free / (1024**3):.2f} GB"
    except Exception:
        pass

    try:
        import psutil

        vm = psutil.virtual_memory()
        metrics["cpu_percent"] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
        metrics["ram_percent"] = f"{vm.percent:.1f}%"
        metrics["ram_used_mb"] = f"{vm.used / (1024**2):.1f} MB"
    except Exception:
        # psutil optional; keep graceful fallback values.
        pass

    return metrics


def show_stats(chat_id):
    """
    Admin'e detaylı sistem istatistiklerini gösterir.

    Kullanıcı sayısı, ders sayısı, aktif oturum sayısı,
    uptime ve dosya boyutları gibi bilgileri içerir.

    :param chat_id: Admin'in chat ID'si
    """
    users = load_admin_users()

    total_users = len(users)
    total_courses = sum(len(u.get("urls", [])) for u in users.values())
    active_sessions = len(get_active_user_sessions())

    # Dosya boyutları
    users_size = Path(USERS_FILE).stat().st_size / 1024 if Path(USERS_FILE).exists() else 0
    data_size = Path(DATA_FILE).stat().st_size / 1024 if Path(DATA_FILE).exists() else 0
    from datetime import date

    log_file_path = Path(LOGS_DIR) / f"app_{date.today().strftime('%Y-%m-%d')}.log"
    log_size = log_file_path.stat().st_size / 1024 if log_file_path.exists() else 0
    runtime = _collect_runtime_metrics()

    stats = (
        "📊 <b>Sistem İstatistikleri</b>\n\n"
        f"👥 <b>Kullanıcılar:</b> {total_users}\n"
        f"📚 <b>Toplam Ders:</b> {total_courses}\n"
        f"🔗 <b>Aktif Oturum:</b> {active_sessions}\n"
        f"⏱ <b>Uptime:</b> {get_uptime()}\n\n"
        "🖥 <b>Anlık Kaynak Kullanımı:</b>\n"
        f"├ CPU: {runtime['cpu_percent']}\n"
        f"├ RAM: {runtime['ram_percent']} ({runtime['ram_used_mb']})\n"
        f"└ Disk: {runtime['disk_percent']} (Boş: {runtime['disk_free_gb']})\n\n"
        f"💾 <b>Dosya Boyutları:</b>\n"
        f"├ users.json: {users_size:.1f} KB\n"
        f"├ ninova_data.json: {data_size:.1f} KB\n"
        f"└ log (bugün): {log_size:.1f} KB"
    )

    logger.info(
        "[admin_metrics] actor=%s | users=%s | courses=%s | sessions=%s | uptime=%s | "
        "cpu=%s | ram=%s | ram_used=%s | disk=%s | disk_free=%s | "
        "users_kb=%.1f | data_kb=%.1f | log_kb=%.1f",
        chat_id,
        total_users,
        total_courses,
        active_sessions,
        get_uptime(),
        runtime["cpu_percent"],
        runtime["ram_percent"],
        runtime["ram_used_mb"],
        runtime["disk_percent"],
        runtime["disk_free_gb"],
        users_size,
        data_size,
        log_size,
    )

    bot.send_message(chat_id, stats, parse_mode="HTML")


def show_user_details(chat_id):
    """
    Tüm kullanıcıların detaylı bilgilerini admin'e gösterir.

    Her kullanıcı için: chat ID, kullanıcı adı, ders sayısı ve
    aktif oturum durumu gösterilir.

    :param chat_id: Admin'in chat ID'si
    """
    users = load_admin_users()

    if not users:
        bot.send_message(chat_id, "Kayıtlı kullanıcı yok.")
        return

    response = "👥 <b>Kullanıcı Detayları</b>\n\n"
    for uid, data in users.items():
        username = data.get("username", "?")
        url_count = len(data.get("urls", []))
        has_session = "✅" if has_user_session(uid) else "❌"
        response += f"🆔 <code>{uid}</code>\n"
        response += f"├ 👤 {username}\n"
        response += f"├ 📚 {url_count} ders\n"
        response += f"└ 🔗 Oturum: {has_session}\n\n"

    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            bot.send_message(chat_id, response[i : i + 4000], parse_mode="HTML")
    else:
        bot.send_message(chat_id, response, parse_mode="HTML")


def show_logs(chat_id, lines=50):
    """
    Güncel log dosyasının son N satırını admin'e gönderir.

    :param chat_id: Admin'in chat ID'si
    :param lines: Gösterilecek maksimum satır sayısı (varsayılan: 50)
    """
    from datetime import date

    log_file = Path(LOGS_DIR) / f"app_{date.today().strftime('%Y-%m-%d')}.log"

    if not log_file.exists():
        bot.send_message(chat_id, "📂 Log dosyası bulunamadı.")
        return

    # Sadece son N satırı oku ve gönder
    try:
        with log_file.open(encoding="utf-8") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            log_text = "".join(last_lines)

            if log_text.strip():
                # Telegram mesaj limiti 4096 karakterdir, gerekirse bölerek gönder
                # <pre> etiketi ile kod bloğu olarak gönderiyoruz
                header = f"📋 <b>Son {len(last_lines)} Log Kaydı (Güncel Dosya)</b>\n\n"

                if len(log_text) > 3500:
                    # Çok uzunsa son 3500 karakteri al (limit 4096)
                    log_text = log_text[-3500:]
                    header = f"📋 <b>Son {len(last_lines)} Log Kaydı (Son 3500 karakter)</b>\n\n"

                bot.send_message(chat_id, f"{header}<pre>{log_text}</pre>", parse_mode="HTML")
            else:
                bot.send_message(chat_id, "📜 Güncel log dosyası boş.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Log okuma hatası: {e}")


def send_backup(chat_id):
    """
    Veritabanı dosyalarını (users.json, ninova_data.json) yedek olarak admin'e gönderir.

    :param chat_id: Admin'in chat ID'si
    """
    files_sent = 0

    for filename in [USERS_FILE, DATA_FILE]:
        filepath = Path(filename)
        if filepath.exists():
            try:
                with filepath.open("rb") as f:
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


def send_broadcast(admin_chat_id, message_text, request_id: str | None = None):
    """
    Tüm kullanıcılara duyuru mesajı gönderir.

    Başarılı ve başarısız gönderim sayılarını admin'e bildirir.

    :param admin_chat_id: Admin'in chat ID'si
    :param message_text: Gönderilecek duyuru mesajı
    """
    users = load_admin_users()
    log_admin_action(
        str(admin_chat_id),
        "broadcast",
        status="started",
        request_id=request_id,
        details=f"users={len(users)}",
    )

    if not users:
        bot.send_message(admin_chat_id, "❌ Kayıtlı kullanıcı yok.")
        log_admin_action(
            str(admin_chat_id),
            "broadcast",
            status="no_users",
            request_id=request_id,
            level="warning",
        )
        return

    success_count = 0
    fail_count = 0
    failed_users = []  # Track failed users with details

    broadcast_msg = f"📢 <b>Sistem Duyurusu</b>\n\n{message_text}"

    for uid in users:
        try:
            bot.send_message(uid, broadcast_msg, parse_mode="HTML")
            success_count += 1
        except Exception as e:
            fail_count += 1
            # Store user ID and error message
            error_msg = str(e)
            # Shorten common errors for readability
            if "bot was blocked" in error_msg:
                error_msg = "Bot engellendi"
            elif "user is deactivated" in error_msg:
                error_msg = "Kullanıcı hesabı kapalı"
            elif "chat not found" in error_msg:
                error_msg = "Chat bulunamadı"
            failed_users.append((uid, error_msg))

    # Build response message
    response = (
        f"📢 <b>Duyuru Gönderildi</b>\n\n✅ Başarılı: {success_count}\n❌ Başarısız: {fail_count}"
    )

    # Add detailed failure list if there are any
    if failed_users:
        response += "\n\n📋 <b>Başarısız Gönderimler:</b>\n"
        for uid, error in failed_users:
            response += f"• <code>{uid}</code> - {error}\n"

    bot.send_message(admin_chat_id, response, parse_mode="HTML")
    log_admin_action(
        str(admin_chat_id),
        "broadcast",
        status="completed",
        request_id=request_id,
        details=f"success={success_count};failed={fail_count}",
    )


def send_direct_message(admin_chat_id, target_id, message_text, request_id: str | None = None):
    """
    Belirli bir kullanıcıya admin mesajı gönderir.

    :param admin_chat_id: Admin'in chat ID'si
    :param target_id: Hedef kullanıcının chat ID'si
    :param message_text: Gönderilecek mesaj
    """
    try:
        log_admin_action(
            str(admin_chat_id),
            "direct_message",
            status="started",
            request_id=request_id,
            target_id=str(target_id),
        )
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
        log_admin_action(
            str(admin_chat_id),
            "direct_message",
            status="completed",
            request_id=request_id,
            target_id=str(target_id),
        )
    except Exception as e:
        bot.send_message(admin_chat_id, f"❌ Mesaj gönderilemedi: {e}")
        log_admin_action(
            str(admin_chat_id),
            "direct_message",
            status="failed",
            request_id=request_id,
            target_id=str(target_id),
            level="error",
        )


@bot.message_handler(func=lambda m: has_admin_state(str(m.chat.id)))
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

    state = get_admin_state(chat_id)
    if not state:
        return

    text = (message.text or "").strip()
    if text in {"🔙 Geri", "⛔ İptal"}:
        pop_admin_state(chat_id)
        bot.send_message(
            chat_id,
            "✅ Admin işlem modu kapatıldı. Ana menüye dönüldü.",
            reply_markup=build_main_keyboard(),
        )
        return

    # State'i temizle
    pop_admin_state(chat_id)

    if state == "waiting_broadcast":
        request_id = f"state-{message.message_id}"
        send_broadcast(chat_id, message.text, request_id=request_id)
    elif state.startswith("waiting_msg_"):
        target_id = state.replace("waiting_msg_", "")
        request_id = f"state-{message.message_id}"
        send_direct_message(chat_id, target_id, message.text, request_id=request_id)
