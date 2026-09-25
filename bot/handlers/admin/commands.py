"""
Admin komutları.
"""

import logging
import os
import sys

from telebot import types

from bot.instance import bot_instance as bot
from core.config import (
    cleanup_inactive_sessions,
    get_active_user_sessions,
)
from core.scheduler import submit_background_task

from .data_helpers import load_admin_users
from .helpers import is_admin, log_admin_action, new_admin_request_id

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
