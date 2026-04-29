"""
Kullanıcı bazlı hata takip modülü.

Ardışık Ninova hatalarını sayar; eşik aşılınca admin/kullanıcıya bildirim gönderir.
Başarılı kontrol sonrası sayacı sıfırlar ve "düzeldi" mesajı atar.

Eşikler:
  3+ ardışık hata → admin'e bildirim (bir kez)
  6+ ardışık hata → kullanıcıya bilgilendirme mesajı (bir kez)
"""

import logging
import threading
from datetime import datetime
from pathlib import Path

from common.config import ADMIN_TELEGRAM_IDS, DATA_DIR, atomic_json_write, load_all_users
from common.log_context import log_with_context
from common.utils import send_telegram_message

logger = logging.getLogger("ninova")

_ERROR_TRACKER_FILE = Path(DATA_DIR) / "error_tracker.json"
_error_tracker_lock = threading.Lock()

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
    """
    error_tracker.json'dan yükler.

    known_user_ids verilirse, artık sistemde bulunmayan kullanıcıların
    kayıtları temizlenir.
    """
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

    _tracker = data


def _save() -> None:
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
    log_with_context(
        logger,
        "warning",
        f"[error_tracker] error recorded: type={error_type} details={error_details}",
        chat_id=chat_id,
        action="error_tracker",
        error_stage=error_stage,
    )

    if error_count >= ERROR_THRESHOLD_ADMIN and not entry["admin_notification_sent"]:
        admin_msg = (
            f"⚠️ <b>Kullanıcıda {error_count} kez Ninova Hataları</b>\n\n"
            f"👤 <b>Kullanıcı:</b> {chat_id} ({username})\n"
            f"🔗 <b>Son Hata Tipi:</b> {entry['last_error_type']}\n"
            f"📝 <b>Detay:</b> {entry['last_error_details']}\n"
            f"🕐 <b>Saat:</b> {entry['last_check_time']}"
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
        entry["admin_notification_sent"] = True

    if error_count >= ERROR_THRESHOLD_USER and not entry["user_notification_sent"]:
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
        entry["user_notification_sent"] = True

    _save()


def record_success(
    chat_id: str,
    username: str = "",
    *,
    last_url: str | None = None,
) -> None:
    """Başarılı kontrol sonrası sayacı sıfırlar; gerekirse 'düzeldi' mesajı gönderir."""
    if chat_id not in _tracker:
        return

    entry = _tracker[chat_id]
    if entry["error_count"] == 0:
        return

    prev_count = entry["error_count"]
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
            f"👤 <b>Kullanıcı:</b> {chat_id} ({username})\n"
            f"🔗 <b>Son Hata Tipi:</b> {entry['last_error_type']}\n"
            f"📊 <b>Hata Sayısı:</b> {prev_count} kez\n"
            f"🕐 <b>Çözüm Saati:</b> {datetime.now().isoformat()}"
        )
        for admin_id in ADMIN_TELEGRAM_IDS:
            if admin_id:
                send_telegram_message(admin_id, admin_msg)

    _tracker[chat_id] = _empty_entry()
    _tracker[chat_id]["last_check_time"] = datetime.now().isoformat()
    _tracker[chat_id]["last_success_time"] = datetime.now().isoformat()
    if last_url:
        _tracker[chat_id]["last_success_url"] = last_url
    _save()


def purge_deleted_users() -> int:
    """
    users.json'da artık bulunmayan kullanıcıların tracker kayıtlarını temizler.
    Temizlenen kayıt sayısını döndürür.
    """
    known = set(load_all_users().keys())
    stale = [k for k in list(_tracker) if k not in known]
    for k in stale:
        del _tracker[k]
    if stale:
        _save()
        logger.info("[error_tracker] %d eski kullanıcı kaydı temizlendi.", len(stale))
    return len(stale)
