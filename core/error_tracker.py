"""Kullanıcı bazlı hata takip modülü.

migrated from: common/error_tracker.py

Ardışık Ninova hatalarını sayar; eşik aşılınca admin/kullanıcıya bildirim gönderir.
Başarılı kontrol sonrası sayacı sıfırlar ve "düzeldi" mesajı atar.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from core.config import ADMIN_TELEGRAM_IDS, DATA_DIR, atomic_json_write, load_all_users
from core.logger import log_with_context
from core.utils import escape_html, send_telegram_message

logger = logging.getLogger("ninova")

_ERROR_TRACKER_FILE = Path(DATA_DIR) / "error_tracker.json"
# _tracker ana döngü, polling thread'leri ve arka plan görevlerinden değiştiriliyor.
# Tüm okuma/yazmalar bu kilit altında yapılır; Telegram gönderimleri kilit dışında.
_error_tracker_lock = threading.RLock()

ERROR_THRESHOLD_ADMIN = 3
ERROR_THRESHOLD_USER = 6

_tracker: dict = {}


def _empty_entry() -> dict:
    return {
        "error_count": 0,
        "last_error_type": None,
        "last_error_details": None,
        "last_error_stage": None,
        "last_error_url": None,
        "user_notification_sent": False,
        "admin_notification_sent": False,
        "last_check_time": datetime.now().isoformat(),
        "last_success_time": None,
        "last_success_url": None,
    }


def load(known_user_ids: set[str] | None = None) -> None:
    """error_tracker.json'dan yükler."""
    global _tracker
    if _ERROR_TRACKER_FILE.exists():
        import json

        try:
            with _ERROR_TRACKER_FILE.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    if known_user_ids is not None:
        data = {k: v for k, v in data.items() if k in known_user_ids}

    with _error_tracker_lock:
        _tracker = data


def _save() -> None:
    """Çağıran _error_tracker_lock'u tutmalı (RLock olduğu için tekrar almak güvenli)."""
    with _error_tracker_lock:
        atomic_json_write(_ERROR_TRACKER_FILE, _tracker)


def record_error(
    chat_id: str,
    error_type: str,
    error_details: str,
    username: str = "",
    *,
    error_stage: str | None = None,
    last_url: str | None = None,
) -> None:
    """Hata sayacını artırır; eşiklere göre bildirim gönderir."""
    with _error_tracker_lock:
        if chat_id not in _tracker:
            _tracker[chat_id] = _empty_entry()

        entry = _tracker[chat_id]
        entry["error_count"] += 1
        entry["last_error_type"] = error_type
        entry["last_error_details"] = error_details
        entry["last_error_stage"] = error_stage
        entry["last_check_time"] = datetime.now().isoformat()
        if last_url:
            entry["last_error_url"] = last_url

        error_count = entry["error_count"]
        notify_admin = error_count >= ERROR_THRESHOLD_ADMIN and not entry["admin_notification_sent"]
        notify_user = error_count >= ERROR_THRESHOLD_USER and not entry["user_notification_sent"]
        if notify_admin:
            entry["admin_notification_sent"] = True
        if notify_user:
            entry["user_notification_sent"] = True
        entry_snapshot = dict(entry)
        _save()

    log_with_context(
        logger,
        "warning",
        f"[error_tracker] error recorded: type={error_type} details={error_details}",
        chat_id=chat_id,
        action="error_tracker",
        error_stage=error_stage,
    )

    if notify_admin:
        admin_msg = (
            f"⚠️ <b>Kullanıcıda {error_count} kez Ninova Hataları</b>\n\n"
            f"👤 <b>Kullanıcı:</b> {chat_id} ({escape_html(username or '')})\n"
            f"🔗 <b>Son Hata Tipi:</b> {escape_html(str(entry_snapshot['last_error_type']))}\n"
            f"📝 <b>Detay:</b> {escape_html(str(entry_snapshot['last_error_details']))}\n"
            f"🕐 <b>Saat:</b> {entry_snapshot['last_check_time']}"
        )
        log_with_context(
            logger,
            "error",
            "[error_tracker] Admin bildirimi gonderiliyor",
            chat_id=chat_id,
            action="error_tracker",
        )
        for admin_id in ADMIN_TELEGRAM_IDS:
            if admin_id:
                send_telegram_message(admin_id, admin_msg, is_error=True)

    if notify_user:
        user_msg = (
            "ℹ️ <b>Bilgilendirme</b>\n\n"
            "Ninova sistemlerinde bir sorun olabilir veya şifrenizin güncelliğini "
            "kontrol etmeniz gerekebilir.\n\n"
            "Eğer şifreniz değişmediyse, Ninova sistemi düzeldiğinde otomatik olarak "
            "mesaj alacaksınız."
        )
        log_with_context(
            logger,
            "info",
            "[error_tracker] Kullanici bilgilendirme gonderiliyor",
            chat_id=chat_id,
            action="error_tracker",
        )
        send_telegram_message(chat_id, user_msg)


def record_success(
    chat_id: str,
    username: str = "",
    *,
    last_url: str | None = None,
) -> None:
    """Başarılı kontrol sonrası sayacı sıfırlar; gerekirse 'düzeldi' mesajı gönderir."""
    with _error_tracker_lock:
        entry = _tracker.get(chat_id)
        if entry is None or entry["error_count"] == 0:
            return

        prev_count = entry["error_count"]
        now_iso = datetime.now().isoformat()
        _tracker[chat_id] = _empty_entry()
        _tracker[chat_id]["last_check_time"] = now_iso
        _tracker[chat_id]["last_success_time"] = now_iso
        if last_url:
            _tracker[chat_id]["last_success_url"] = last_url
        _save()

    log_with_context(
        logger,
        "info",
        "[error_tracker] Sorun duzeldi",
        chat_id=chat_id,
        action="error_tracker",
    )

    if entry.get("user_notification_sent"):
        send_telegram_message(
            chat_id,
            "✅ <b>Sistem Normale Döndü</b>\n\n"
            "Ninova bağlantısı başarıyla sağlandı. "
            "Normal bildirimler yeniden başlayacaktır.",
        )
        log_with_context(
            logger,
            "info",
            "[error_tracker] Kullaniciya duzeldi bildirimi gonderildi",
            chat_id=chat_id,
            action="error_tracker",
        )

    if entry.get("admin_notification_sent"):
        admin_msg = (
            f"✅ <b>Ninova Sorunu Çözüldü</b>\n\n"
            f"👤 <b>Kullanıcı:</b> {chat_id} ({escape_html(username or '')})\n"
            f"🔗 <b>Son Hata Tipi:</b> {escape_html(str(entry['last_error_type']))}\n"
            f"📊 <b>Hata Sayısı:</b> {prev_count} kez\n"
            f"🕐 <b>Çözüm Saati:</b> {datetime.now().isoformat()}"
        )
        for admin_id in ADMIN_TELEGRAM_IDS:
            if admin_id:
                send_telegram_message(admin_id, admin_msg)


def purge_deleted_users() -> int:
    """users.json'da artık bulunmayan kullanıcıların tracker kayıtlarını temizler."""
    known = set(load_all_users().keys())
    with _error_tracker_lock:
        stale = [k for k in list(_tracker) if k not in known]
        for k in stale:
            del _tracker[k]
        if stale:
            _save()
        logger.info("[error_tracker] %d eski kullanıcı kaydı temizlendi.", len(stale))
    return len(stale)
