import json
import logging
import random
import signal
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from telebot import types as tg_types

import core.error_tracker as error_tracker
from bot import bot, set_check_callback, update_last_check_time
from bot.callback_parsing import url_token
from core.config import (
    CHECK_INTERVAL,
    DATA_DIR,
    LOGS_DIR,
    SESSION_CLEANUP_INTERVAL,
    atomic_json_write,
    cleanup_inactive_sessions,
    console,
    get_cache_stats,
    get_user_session,
    load_all_users,
    sync_cache_to_disk,
)
from core.logger import clear_log_context, set_log_context, setup_logging
from core.storage import modify_user, update_user_grades
from core.utils import (
    decrypt_password,
    escape_html,
    get_file_icon,
    load_saved_grades,
    send_telegram_message,
)
from services.ari24.client import Ari24Client
from services.ninova import (
    LoginFailedError,
    get_grades,
    login_to_ninova,
)
from services.ninova.diff_engine import compare_course_data
from services.sks.announcer import check_and_announce_sks_menu

# Logging yapılandırması
_logs_dir = Path(LOGS_DIR)
_log_handler = setup_logging(_logs_dir)


logger = logging.getLogger("ninova")

# Son kontrol zamanı (global) - Live display'de kullanılacak
LAST_CHECK_DISPLAY_TIME = None

# Terminal çıktı ayarları (gürültüyü azaltmak için)
SHOW_VERBOSE_TERMINAL = False
LIVE_REFRESH_PER_SECOND = 0.5
LIVE_STATUS_UPDATE_EVERY_SECONDS = 10
POLLING_TIMEOUT_SECONDS = 20
POLLING_LONG_TIMEOUT_SECONDS = 20
POLLING_LOG_LEVEL = logging.WARNING
SHUTDOWN_EVENT = threading.Event()
POLLING_THREAD: threading.Thread | None = None
_SHUTDOWN_LOCK = threading.Lock()

# Aynı anda iki genel kontrol (ana döngü + admin "force") veya aynı kullanıcı için iki
# kontrol (otomatik + manuel) çalışırsa ikisi de aynı kayıtlı veriye göre fark hesaplayıp
# aynı bildirimi iki kez gönderiyor, sonra birbirinin kaydını eziyordu.
_GLOBAL_CHECK_LOCK = threading.Lock()
_USER_CHECK_LOCKS: dict[str, threading.Lock] = {}
_USER_CHECK_LOCKS_GUARD = threading.Lock()


def _user_check_lock(chat_id: str) -> threading.Lock:
    with _USER_CHECK_LOCKS_GUARD:
        return _USER_CHECK_LOCKS.setdefault(str(chat_id), threading.Lock())


# error_tracker: yükle ve artık var olmayan kullanıcıları temizle
error_tracker.load(known_user_ids=set(load_all_users().keys()))
_SHUTDOWN_DONE = False


def emit_terminal_and_log(message: str, level: str = "info") -> None:
    """Emit important summaries to both terminal and logger."""
    log_method = getattr(logger, level, logger.info)
    log_method(message)
    style = {
        "info": "[cyan]",
        "warning": "[yellow]",
        "error": "[bold red]",
        "critical": "[bold red]",
    }.get(level, "[cyan]")
    console.print(f"{style}{message}")


def graceful_shutdown(reason: str) -> None:
    """Stop polling and flush resources exactly once."""
    global _SHUTDOWN_DONE
    with _SHUTDOWN_LOCK:
        if _SHUTDOWN_DONE:
            return
        _SHUTDOWN_DONE = True

    SHUTDOWN_EVENT.set()
    emit_terminal_and_log(f"Shutdown başlatıldı: {reason}", level="warning")

    if bot:
        try:
            bot.stop_polling()
        except Exception as e:
            logger.exception(f"Polling stop failed: {e}")

    global POLLING_THREAD
    if POLLING_THREAD and POLLING_THREAD.is_alive():
        POLLING_THREAD.join(timeout=5)

    try:
        closed = cleanup_inactive_sessions(force=True)
        logger.info(f"Shutdown session cleanup: {closed} closed")
    except Exception as e:
        logger.exception(f"Shutdown session cleanup failed: {e}")

    try:
        sync_cache_to_disk()
    except Exception as e:
        logger.exception(f"Shutdown cache sync failed: {e}")


def _start_polling_thread() -> None:
    """Start Telegram polling in a daemon thread with resilient defaults."""
    global POLLING_THREAD
    POLLING_THREAD = threading.Thread(
        target=bot.infinity_polling,
        kwargs={
            "skip_pending": True,
            "timeout": POLLING_TIMEOUT_SECONDS,
            "long_polling_timeout": POLLING_LONG_TIMEOUT_SECONDS,
            "logger_level": POLLING_LOG_LEVEL,
        },
        daemon=True,
    )
    POLLING_THREAD.start()


def show_users_table():
    """
    Kayıtlı kullanıcıları tablo formatında gösterir.

    Her kullanıcı için chat ID, kullanıcı adı, ders sayısı ve
    son aktivite zamanı gösterilir.
    """
    users = load_all_users()
    if not users:
        console.print("[yellow]Henüz kayıtlı kullanıcı yok.[/yellow]")
        return

    table = Table(title="📋 Kayıtlı Kullanıcılar", show_header=True, header_style="bold magenta")
    table.add_column("Chat ID", style="cyan", no_wrap=True)
    table.add_column("Kullanıcı Adı", style="green")
    table.add_column("Ders Sayısı", style="yellow", justify="center")
    table.add_column("Son Aktivite", style="blue")

    for chat_id, user_data in users.items():
        username = user_data.get("username", "Bilinmiyor")
        urls_count = len(user_data.get("urls", []))
        last_check_raw = user_data.get("last_check")
        if last_check_raw:
            try:
                last_check_dt = datetime.fromisoformat(last_check_raw)
                last_check = last_check_dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                last_check = last_check_raw
        else:
            last_check = "Hiç"
        table.add_row(str(chat_id), username, str(urls_count), last_check)

    console.print(table)
    console.print(f"\n[dim]Toplam {len(users)} kullanıcı kayıtlı.[/dim]")


# Dashboard layout - Future için hazırlanmış, şu an kullanılmıyor


def check_ari24_updates():
    """
    Checks Arı24 events and notifies subscribed users.
    """
    state_file = Path(DATA_DIR) / "ari24_state.json"
    try:
        if Path(state_file).exists():
            try:
                with Path(state_file).open() as f:
                    state = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Arı24 state file corrupted: {state_file} - {e}")
                state = {"notified_urls": []}
        else:
            state = {"notified_urls": []}
    except Exception as e:
        logger.exception(f"Error loading Arı24 state: {e}")
        state = {"notified_urls": []}

    try:
        client = Ari24Client()
        events = client.get_upcoming_events()
        notified_urls = set(state.get("notified_urls", []))
        new_urls = []

        users = load_all_users()

        for event in events:
            url = event["link"]
            if url in notified_urls:
                continue

            # Filtering out past events
            # If the event has a parsable date, and it's before today 00:00, ignore it.
            # We use a slight buffer or just today 00:00.
            if event["date_dt"]:
                now = datetime.now()
                # Compare with Today End or Beginning?
                # User says "past events". So anything before "Now" effectively.
                # But let's be generous and say anything before Today 00:00 is definitely past.
                if event["date_dt"] < now.replace(hour=0, minute=0, second=0, microsecond=0):
                    continue

            club = event["organizer"]
            new_urls.append(url)

            # Notify subscribers
            for chat_id, user_data in users.items():
                subs = user_data.get("subscriptions", [])
                # Partial match or exact match?
                # Scraper returns full name. Handlers use full name.
                # So exact match check is fine.
                if club in subs:
                    caption = (
                        f"🔔 <b>Yeni Etkinlik: {club}</b>\n\n"
                        f"📅 <b>{event['title']}</b>\n"
                        f"🕒 {event['date_str']}\n"
                        f"🔗 <a href='{url}'>Detaylar</a>"
                    )
                    try:
                        if event["image_url"]:
                            bot.send_photo(
                                chat_id, event["image_url"], caption=caption, parse_mode="HTML"
                            )
                        else:
                            bot.send_message(chat_id, caption, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Failed to send ari24 notification to {chat_id}: {e}")

        if new_urls:
            # set sırasız olduğundan list(set)[-500:] rastgele öğeleri atıyordu; sırayı koru.
            old_urls = [u for u in state.get("notified_urls", []) if u not in new_urls]
            state["notified_urls"] = (old_urls + new_urls)[-500:]  # Keep last 500

        # --- NEWS CHECK ---
        notified_news_list = state.get("notified_news", [])
        notified_news = set(notified_news_list)
        current_news = client.get_news(limit=5)
        new_news_items = [item for item in current_news if item["link"] not in notified_news]

        if new_news_items:
            # Broadcast to ALL users
            # Reverse to send oldest new item first
            for item in reversed(new_news_items):
                caption = (
                    f"📰 <b>Yeni Haber: {item['title']}</b>\n"
                    f"🔗 <a href='{item['link']}'>Haberi Oku</a>"
                )
                for chat_id in users:
                    try:
                        if item.get("image_url"):
                            bot.send_photo(
                                chat_id, item["image_url"], caption=caption, parse_mode="HTML"
                            )
                        else:
                            bot.send_message(chat_id, caption, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Failed to send news to {chat_id}: {e}")

                notified_news_list.append(item["link"])

            # Sıra korunmalı: rastgele kırpma güncel haberleri listeden atıp tüm
            # kullanıcılara tekrar gönderilmesine yol açıyordu.
            state["notified_news"] = notified_news_list[-200:]  # Keep last 200

        atomic_json_write(state_file, state)

    except Exception as e:
        logger.error(f"Ari24 check error: {e}")


def check_daily_bulletin():
    """
    Checks if it is 08:00 AM and sends daily bulletin to subscribed users.
    Should be called periodically (e.g. every minute or so).
    Manages state to avoid multiple sends in the same day.
    """
    now = datetime.now()
    # Check if time is 08:xx
    if now.hour != 8:
        return

    state_file = Path(DATA_DIR) / "daily_bulletin_state.json"
    today_str = now.strftime("%Y-%m-%d")

    try:
        if Path(state_file).exists():
            with Path(state_file).open() as f:
                state = json.load(f)
        else:
            state = {"last_sent_date": ""}

        if state.get("last_sent_date") == today_str:
            return  # Already sent today

        # Send Bulletin
        client = Ari24Client()
        events = client.get_weekly_events()  # Allows fetching next 14 days

        # Group events
        today_date = now.date()
        today_events = []
        upcoming_events = []

        for ev in events:
            if not ev["date_dt"]:
                continue

            ev_date = ev["date_dt"].date()
            if ev_date == today_date:
                today_events.append(ev)
            elif ev_date > today_date:
                upcoming_events.append(ev)

        if not today_events and not upcoming_events:
            # Nothing at all?
            # Mark sent and return
            state["last_sent_date"] = today_str
            atomic_json_write(state_file, state)
            return

        date_formatted = now.strftime("%d.%m.%Y")
        bulletin_message = f"☀️ <b>GÜNLÜK BÜLTEN | {date_formatted}</b>\n\n"

        if today_events:
            bulletin_message += "📅 <b>BUGÜN:</b>\n"
            for ev in today_events:
                bulletin_message += (
                    f"▫️ {ev['organizer']} - {ev['title']}\n"
                    f"⏰ {ev['date_str']}\n"
                    f"🔗 <a href='{ev['link']}'>İncele</a>\n\n"
                )
        else:
            bulletin_message += "📅 <b>BUGÜN:</b>\n<i>Etkinlik bulunmuyor.</i>\n\n"

        if upcoming_events:
            bulletin_message += "🗓 <b>YAKLAŞANLAR (Bu hafta + Gelecek Hafta):</b>\n"
            # Maybe limit upcoming to avoid huge messages?
            # Limit to 10 upcoming events
            for ev in upcoming_events[:15]:
                bulletin_message += (
                    f"▫️ {ev['date_str']} | {ev['organizer']}\n   <b>{ev['title']}</b>\n\n"
                )
            if len(upcoming_events) > 15:
                bulletin_message += f"<i>... ve {len(upcoming_events) - 15} etkinlik daha.</i>\n"

        bulletin_message += (
            "\n\n🔔 Belirli kulüplerin etkinliklerini takip etmek için - <i>Arı24 → Abone Ol</i>\n"
            "<i>Günlük bülteni kapatmak için - Arı24 → Günlük Bülten</i>"
        )

        users = load_all_users()
        for chat_id, user_data in users.items():
            if user_data.get("daily_subscription", False):
                try:
                    bot.send_message(
                        chat_id, bulletin_message, parse_mode="HTML", disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"Failed to send daily bulletin to {chat_id}: {e}")

        # Update state
        state["last_sent_date"] = today_str
        atomic_json_write(state_file, state)

    except Exception as e:
        logger.error(f"Daily bulletin error: {e}")


def _send_file_notifications(
    chat_id: str,
    new_file_notifications: list,
    updated_file_notifications: list,
    assignment_source_notifications: list,
) -> None:
    """Yeni/güncellenen dosyalar ve ödev kaynak dosyaları için "İndir" butonlu mesajlar gönderir."""
    if not (
        new_file_notifications or updated_file_notifications or assignment_source_notifications
    ):
        return

    # Buton indeksleri callback handler'larında kayıtlı ders sırasına göre çözülüyor;
    # kayıt yapıldıktan sonra diskteki sırayı kullan. Ek olarak dosya URL token'ı
    # eklenir; sıra sonradan değişse de buton doğru dosyayı bulur.
    user_grades = load_saved_grades().get(chat_id, {})
    urls_list = list(user_grades.keys())

    def _file_token(course_url: str, file_idx: int) -> str:
        files = user_grades.get(course_url, {}).get("files", [])
        return url_token(files[file_idx].get("url", "")) if file_idx < len(files) else ""

    def _source_token(course_url: str, assign_idx: int, sf_idx: int) -> str:
        assignments = user_grades.get(course_url, {}).get("assignments", [])
        if assign_idx >= len(assignments):
            return ""
        source_files = assignments[assign_idx].get("source_files", [])
        if sf_idx >= len(source_files):
            return ""
        return url_token(source_files[sf_idx].get("url", ""))

    def _send(text: str, callback_data: str, what: str) -> None:
        markup = tg_types.InlineKeyboardMarkup()
        markup.add(tg_types.InlineKeyboardButton("📥 İndir", callback_data=callback_data))
        try:
            bot.send_message(
                chat_id,
                text,
                reply_markup=markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"{what} notification send error for {chat_id}: {e}")
        time.sleep(1)

    for course_url, file_course_name, file_idx, file_name in new_file_notifications:
        if course_url not in urls_list:
            continue
        basename = file_name.split("/")[-1]
        _send(
            f"📚 <b>{escape_html(file_course_name)}</b>\n"
            f"{get_file_icon(basename)} <b>YENİ DOSYA:</b> {escape_html(basename)}",
            f"dl_{urls_list.index(course_url)}_{file_idx}_{_file_token(course_url, file_idx)}",
            "File",
        )

    for (
        course_url,
        file_course_name,
        file_idx,
        file_name,
        change_type,
    ) in updated_file_notifications:
        if course_url not in urls_list:
            continue
        basename = file_name.split("/")[-1]
        _send(
            f"📚 <b>{escape_html(file_course_name)}</b>\n"
            f"{get_file_icon(basename)} <b>DOSYA {change_type}:</b> {escape_html(basename)}",
            f"dl_{urls_list.index(course_url)}_{file_idx}_{_file_token(course_url, file_idx)}",
            "File update",
        )

    for (
        course_url,
        file_course_name,
        assign_idx,
        sf_idx,
        file_name,
        file_size,
        assign_name,
        is_new_assign,
    ) in assignment_source_notifications:
        if course_url not in urls_list:
            continue
        label = "YENİ ÖDEV KAYNAK DOSYASI" if is_new_assign else "YENİ KAYNAK DOSYA"
        _send(
            f"📚 <b>{escape_html(file_course_name)}</b>\n"
            f"📅 {escape_html(assign_name)}\n"
            f"{get_file_icon(file_name)} <b>{label}:</b> {escape_html(file_name)} "
            f"({escape_html(file_size)})",
            f"asf_{urls_list.index(course_url)}_{assign_idx}_{sf_idx}_"
            f"{_source_token(course_url, assign_idx, sf_idx)}",
            "Assignment source file",
        )


def _touch_last_check(chat_id: str) -> None:
    """last_check alanını günceller; kullanıcı arada silindiyse onu yeniden yaratmaz."""
    now_iso = datetime.now().isoformat()

    def _set(data):
        data["last_check"] = now_iso

    modify_user(chat_id, _set)


def _bookkeeping_changed(updated_courses: dict, saved_courses: dict) -> bool:
    """
    Kullanıcıya görünen bir değişiklik olmasa da kaydedilmesi gereken iç durum
    değişti mi? (ödev detay önbelleği, şüpheli boş dosya listesi sayacı)
    """

    def _meta(course):
        return (
            course.get("files_suspect_count", 0),
            {
                a.get("id"): (a.get("detail_fetched_at"), a.get("list_signature"))
                for a in course.get("assignments", [])
            },
        )

    return any(
        _meta(course) != _meta(saved_courses.get(url, {}))
        for url, course in updated_courses.items()
    )


def _process_user_results(
    chat_id: str,
    username: str,
    user_session,
    all_current_grades: dict,
    *,
    silent: bool,
    include_reminders: bool,
    changes_table: Table | None = None,
) -> list[str]:
    """
    Bir kullanıcının çekilen ders verilerini kayıtla karşılaştırır, değişiklik varsa
    kaydeder ve bildirimleri gönderir. Otomatik ve manuel kontrolün ortak kısmı.

    :return: Değişiklik açıklamaları listesi
    """
    user_saved_grades = load_saved_grades().get(chat_id, {})
    all_changes = []
    telegram_messages = []
    updated_courses = {}
    new_file_notifications = []  # (course_url, course_name, file_idx, file_name)
    updated_file_notifications = []  # (course_url, course_name, file_idx, file_name, change_type)
    assignment_source_notifications = []  # (course_url, course_name, assign_idx, sf_idx, ...)

    for url, current_data in all_current_grades.items():
        course_name = current_data.get("course_name", "Bilinmeyen Ders")
        saved_data = user_saved_grades.get(url, {})

        (
            sections_changes,
            changes,
            new_file_entries,
            updated_file_entries,
            assignment_source_entries,
        ) = compare_course_data(
            current_data,
            saved_data,
            user_session,
            course_name,
            include_reminders=include_reminders,
            include_console_log=changes_table is not None,
            username=username,
            changes_table=changes_table,
        )

        all_changes.extend(changes)
        new_file_notifications.extend(
            (url, course_name, file_idx, file_name) for file_idx, file_name in new_file_entries
        )
        updated_file_notifications.extend(
            (url, course_name, file_idx, file_name, change_type)
            for file_idx, file_name, change_type in updated_file_entries
        )
        assignment_source_notifications.extend(
            (url, course_name, *entry) for entry in assignment_source_entries
        )

        if sections_changes:
            telegram_messages.append(
                f"📚 <b>{escape_html(course_name)}</b>\n\n" + "\n\n".join(sections_changes)
            )

        files_to_save = current_data.get("files", [])
        files_suspect_count = saved_data.get("files_suspect_count", 0)
        if current_data.get("_files_suspect"):
            files_to_save = saved_data.get("files", [])
            files_suspect_count = current_data.get("_files_suspect_count", files_suspect_count)
        else:
            files_suspect_count = 0

        updated_courses[url] = {
            "course_name": course_name,
            "grades": current_data.get("grades", {}),
            "assignments": current_data.get("assignments", []),
            "files": files_to_save,
            "announcements": current_data.get("announcements", []),
            "files_suspect_count": files_suspect_count,
        }

    if not all_changes:
        # Değişiklik yoksa bile iç durum (ödev detay önbelleği, şüpheli boş dosya
        # listesi sayacı) ilerlediyse sessizce kaydet. Aksi halde detaylar her döngüde
        # yeniden çekilir ve sayaç hiç artmadığı için gerçekten silinen dosyalar
        # asla kabul edilmez.
        if _bookkeeping_changed(updated_courses, user_saved_grades):
            update_user_grades(chat_id, updated_courses)
        return all_changes

    # Önce kaydet, sonra bildir: gönderim sırasında hata olursa bir sonraki kontrolde
    # aynı bildirimler tekrar gitmesin. Sadece bu kullanıcının dersleri güncellenir.
    update_user_grades(chat_id, updated_courses)

    if not silent:
        for t_msg in telegram_messages:
            send_telegram_message(chat_id, t_msg)
            time.sleep(1)
        _send_file_notifications(
            chat_id,
            new_file_notifications,
            updated_file_notifications,
            assignment_source_notifications,
        )

    return all_changes


def check_user_updates(
    chat_id: str,
    course_idx: int | None = None,
    silent: bool = False,
    request_id: str | None = None,
):
    """
    Belirli bir kullanıcının notlarını kontrol eder.

    Bot /kontrol komutu veya manuel butonlar için kullanılır. Sadece belirtilen
    kullanıcının derslerini (veya opsiyonel olarak tek bir dersi) tarar,
    değişiklikleri kontrol eder ve bildirim gönderir.

    :param chat_id: Kontrol edilecek kullanıcının chat ID'si
    :param course_idx: (Opsiyonel) Sadece bu indeksteki dersi kontrol et
        (ders menüsündeki sıra, yani kayıtlı ders verisinin sırası)
    :param silent: (Opsiyonel) Bildirim göndermeden sadece verileri güncelle (True/False)
    :return: Başarı durumu ve mesaj içeren dict
    """
    chat_id = str(chat_id)
    with _user_check_lock(chat_id):
        try:
            return _check_user_updates_locked(chat_id, course_idx, silent, request_id)
        finally:
            clear_log_context()


def _check_user_updates_locked(
    chat_id: str,
    course_idx: int | None,
    silent: bool,
    request_id: str | None,
):
    request_id = request_id or f"chk-{chat_id}-{int(time.time())}"
    set_log_context(chat_id=str(chat_id), action="check_user_updates", request_id=request_id)
    user_data = load_all_users().get(chat_id)
    logger.info(
        "[user] actor=%s | action=check_user_updates | status=started | request_id=%s | "
        "details=course_idx=%s;silent=%s",
        chat_id,
        request_id,
        course_idx,
        silent,
    )

    if not user_data:
        logger.warning(
            "[user] actor=%s | action=check_user_updates | status=missing_user | request_id=%s",
            chat_id,
            request_id,
        )
        return {"success": False, "message": "Kullanıcı bilgileri bulunamadı."}

    all_urls = user_data.get("urls", [])

    if not all_urls:
        logger.warning(
            "[user] actor=%s | action=check_user_updates | status=no_courses | request_id=%s",
            chat_id,
            request_id,
        )
        return {"success": False, "message": "Takip edilen ders bulunamadı."}

    # Eğer tek bir ders istenmişse filtrele
    if course_idx is not None:
        # Menüdeki "Kontrol Et" butonları kayıtlı ders verisinin sırasını kullanıyor;
        # users.json'daki URL sırası farklı olabildiğinden yanlış ders kontrol ediliyordu.
        menu_urls = list(load_saved_grades().get(chat_id, {}).keys()) or all_urls
        if course_idx < 0 or course_idx >= len(menu_urls):
            logger.warning(
                "[user] actor=%s | action=check_user_updates | status=invalid_course_idx | request_id=%s",
                chat_id,
                request_id,
            )
            return {"success": False, "message": "Geçersiz ders indeksi."}
        urls_to_scan = [menu_urls[course_idx]]
    else:
        urls_to_scan = all_urls

    username = user_data.get("username")
    encrypted_password = user_data.get("password")

    if not username or not encrypted_password:
        logger.warning(
            "[user] actor=%s | action=check_user_updates | status=missing_credentials | request_id=%s",
            chat_id,
            request_id,
        )
        return {"success": False, "message": "Kullanıcı bilgileri eksik."}

    password = decrypt_password(encrypted_password)
    if password is None:
        logger.error(
            "[user] actor=%s | action=check_user_updates | status=decrypt_failed | request_id=%s",
            chat_id,
            request_id,
        )
        error_tracker.record_error(
            chat_id,
            "DECRYPT_ERROR",
            "Şifre çözülemedi",
            username,
            error_stage="decrypt",
        )
        return {"success": False, "message": "Şifre çözme hatası."}

    # Get user session (managed by SessionManager)
    user_session = get_user_session(chat_id)
    all_current_grades = {}
    saved = load_saved_grades().get(chat_id, {})

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        scan_msg = (
            f"[yellow]{username} ({len(urls_to_scan)} ders) taranıyor..."
            if course_idx is None
            else f"[yellow]{username} (Tek ders) taranıyor..."
        )
        task = progress.add_task(scan_msg, total=len(urls_to_scan))
        for url in urls_to_scan:
            try:
                grades = get_grades(
                    user_session, url, chat_id, username, password, previous=saved.get(url)
                )
                if grades:
                    all_current_grades[url] = grades
            except LoginFailedError as e:
                logger.error(
                    "[user] actor=%s | action=check_user_updates | status=login_failed | "
                    "request_id=%s | error_type=%s | details=%s",
                    chat_id,
                    request_id,
                    e.error_type,
                    e.message,
                )
                error_tracker.record_error(
                    chat_id,
                    e.error_type,
                    str(e.message),
                    username,
                    error_stage="login",
                    last_url=url,
                )
                return {"success": False, "message": "Ninova bağlantı hatası."}

            progress.update(task, advance=1)
            time.sleep(0.2)

    # Başarılı veri çekimi - hata sayacını sıfırla
    if all_current_grades:
        last_url = next(iter(all_current_grades.keys()), None)
        error_tracker.record_success(chat_id, username, last_url=last_url)

    all_changes = _process_user_results(
        chat_id,
        username,
        user_session,
        all_current_grades,
        silent=silent,
        include_reminders=False,
    )

    # Sadece last_check alanını güncelle. Eskiden taramanın başında okunan tüm users.json
    # kopyası geri yazılıyordu; tarama sürerken yapılan değişiklikler (ör. eklenen ders)
    # kayboluyordu.
    _touch_last_check(chat_id)

    # Son kontrol zamanını güncelle
    global LAST_CHECK_DISPLAY_TIME
    LAST_CHECK_DISPLAY_TIME = datetime.now().strftime("%H:%M:%S")

    result_msg = f"✅ Kontrol tamamlandı ({len(all_changes)} değişiklik)"
    if not all_changes:
        result_msg = "✅ Kontrol tamamlandı (değişiklik yok)"

    logger.info(
        "[user] actor=%s | action=check_user_updates | status=completed | request_id=%s | details=changes=%s;scanned=%s",
        chat_id,
        request_id,
        len(all_changes),
        len(urls_to_scan),
    )
    return {"success": True, "message": result_msg, "changes": len(all_changes)}


def check_for_updates():
    """
    Tüm kullanıcılar için ders verilerini tarar ve güncellemeleri kontrol eder.

    Ana kontrol döngüsünde periyodik olarak çalışır. Her kullanıcı için:
    - Notları kontrol eder
    - Ödev durumlarını kontrol eder
    - Dosya güncellemelerini kontrol eder
    - Duyuruları kontrol eder
    - Ödev hatırlatmaları gönderir

    Yeni veya güncellenmiş içerik varsa Telegram bildirim gönderir.
    Başka bir genel kontrol sürüyorsa (ör. admin force + ana döngü) hemen döner.

    :return: Kontrol çalıştıysa True, başka kontrol sürdüğü için atlandıysa False
    """
    if not _GLOBAL_CHECK_LOCK.acquire(blocking=False):
        logger.warning("Genel kontrol zaten çalışıyor, bu istek atlandı.")
        return False
    try:
        _check_for_updates_locked()
        return True
    finally:
        _GLOBAL_CHECK_LOCK.release()


def _check_for_updates_locked():
    update_last_check_time()

    # Değişiklikler tablosu
    changes_table = Table(title="🔄 Bu Kontrol Dönemindeki Değişiklikler")
    changes_table.add_column("Kullanıcı", style="bold blue", no_wrap=True)
    changes_table.add_column("Ders", style="bold green")
    changes_table.add_column("Değişiklik", style="yellow")

    users = load_all_users()
    msg = f"Kontrol Başlatıldı - {len(users)} kullanıcı"
    logger.info(msg)
    console.rule(f"[bold cyan][{time.strftime('%H:%M:%S')}] {msg}")
    # fix: guard against corrupt users.json returning {} (BUG-E1)
    if not users:
        logger.warning("Kullanıcı listesi boş veya yüklenemedi, kontrol atlanıyor.")
        return
    changed_usernames = set()
    total_changes_count = 0

    for chat_id, user_data in users.items():
        if SHUTDOWN_EVENT.is_set():
            break
        request_id = f"auto-{chat_id}-{int(time.time())}"
        set_log_context(chat_id=str(chat_id), action="check_for_updates", request_id=request_id)
        try:
            with _user_check_lock(chat_id):
                changes = _check_single_user(chat_id, user_data, changes_table)
            if changes:
                changed_usernames.add(user_data.get("username") or str(chat_id))
                total_changes_count += len(changes)
        except Exception as e:
            # Tek bir kullanıcıdaki beklenmeyen hata diğer kullanıcıların kontrolünü
            # (ve ana döngüyü) durdurmasın.
            logger.exception(f"[{chat_id}] Kullanıcı kontrolü sırasında beklenmeyen hata: {e}")
        finally:
            clear_log_context()

    logger.info("Kontrol tamamlandı.")

    # Değişiklikler tablosunu göster (eğer değişiklik varsa)
    if SHOW_VERBOSE_TERMINAL and changes_table.rows:
        console.print()
        console.print(changes_table)

    changed_users = len(changed_usernames)
    summary = (
        f"Kontrol özeti: {len(users)} kullanıcı tarandı, "
        f"{total_changes_count} değişiklik, {changed_users} kullanıcı etkilendi"
    )
    emit_terminal_and_log(summary, level="info")

    # Son kontrol zamanını güncelle (Live display'de kullanmak için)
    global LAST_CHECK_DISPLAY_TIME
    LAST_CHECK_DISPLAY_TIME = datetime.now().strftime("%H:%M:%S")


def _check_single_user(chat_id: str, user_data: dict, changes_table: Table) -> list[str]:
    """Otomatik kontrolde tek bir kullanıcının tüm derslerini tarar."""
    urls = user_data.get("urls", [])
    if not urls:
        return []

    username = user_data.get("username")
    encrypted_password = user_data.get("password")

    if not username or not encrypted_password:
        logger.warning(f"Kullanıcı bilgileri eksik ({chat_id}), pas geçiliyor.")
        return []

    password = decrypt_password(encrypted_password)
    if password is None:
        logger.error(f"Şifre çözülemedi ({chat_id}), pas geçiliyor.")
        error_tracker.record_error(
            chat_id,
            "DECRYPT_ERROR",
            "Şifre çözülemedi",
            username,
            error_stage="decrypt",
        )
        return []

    if SHOW_VERBOSE_TERMINAL:
        console.print(f"[bold cyan]Kullanıcı kontrol ediliyor: {chat_id}")

    # Get user session (managed by SessionManager)
    user_session = get_user_session(chat_id)
    saved = load_saved_grades().get(chat_id, {})

    # Dersler aşağıda aynı oturumla paralel çekiliyor. Oturumu önce tek seferde
    # doğrula/yenile: aksi halde oturum yokken (veya ağ koptuğunda) 5 thread'in her biri
    # sırayla backoff'lu login denemesi yapıyor, kullanıcı başına dakikalarca bekleniyordu.
    # Tarama sırasında oturum düşerse yeniden giriş auth.get_user_lock ile tekilleşir ve
    # login sayfası dönen bölümler failed_sections ile kayıtlı veriyi korur.
    try:
        login_to_ninova(user_session, chat_id, username, password, quiet=True)
    except LoginFailedError as e:
        logger.error(
            "[%s] %s - LoginFailedError: type=%s, details=%s",
            chat_id,
            username,
            e.error_type,
            e.message,
        )
        error_tracker.record_error(
            chat_id, e.error_type, str(e.message), username, error_stage="login"
        )
        return []

    all_current_grades = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[yellow]{username} ({len(urls)} ders) taranıyor...",
            total=len(urls),
        )

        # Paralel tarama için ThreadPoolExecutor kullan
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(
                    get_grades,
                    user_session,
                    url,
                    chat_id,
                    username,
                    password,
                    previous=saved.get(url),
                ): url
                for url in urls
            }

            login_error_sent = False
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    grades = future.result()
                    if grades:
                        all_current_grades[url] = grades
                except LoginFailedError as e:
                    if not login_error_sent:
                        logger.error(
                            "[%s] %s - LoginFailedError: type=%s, details=%s",
                            chat_id,
                            username,
                            e.error_type,
                            e.message,
                        )
                        error_tracker.record_error(
                            chat_id,
                            e.error_type,
                            str(e.message),
                            username,
                            error_stage="login",
                            last_url=url,
                        )
                        login_error_sent = True
                    else:
                        logger.debug("[%s] %s - Login error on %s: %s", chat_id, username, url, e)
                except Exception as e:
                    logger.error(f"[{chat_id}] Ders tarama hatası ({url}): {e}")
                finally:
                    progress.update(task, advance=1)

    # Başarılı veri çekimi → hata sayacını sıfırla, düzeldi mesajı gönder
    if all_current_grades:
        last_url = next(iter(all_current_grades.keys()), None)
        error_tracker.record_success(chat_id, username, last_url=last_url)

    all_changes = _process_user_results(
        chat_id,
        username,
        user_session,
        all_current_grades,
        silent=False,
        include_reminders=True,
        changes_table=changes_table,
    )

    if all_changes:
        logger.info(f"Değişiklik tespit edildi: {chat_id} - {len(all_changes)} öğe")
        if SHOW_VERBOSE_TERMINAL:
            console.print(
                Panel(
                    "\n".join(all_changes),
                    title=f"[bold magenta]DEĞİŞİKLİK ({chat_id})",
                    border_style="magenta",
                )
            )
    elif SHOW_VERBOSE_TERMINAL:
        console.print(f"[dim]Değişiklik yok ({chat_id})")

    # fix: save last_check per-user atomically (BUG-C3)
    _touch_last_check(chat_id)
    return all_changes


if __name__ == "__main__":
    set_check_callback(check_for_updates)

    users = load_all_users()
    logger.info(f"Uygulama başlatıldı. Kayıtlı kullanıcı: {len(users)}")
    console.print(
        Panel.fit(
            "[bold green]Ninova Çok Kullanıcılı Not Takipçisi Başlatıldı[/bold green]\n"
            f"[blue]Kayıtlı kullanıcı sayısı: {len(users)}[/blue]\n"
            "[white]Çıkmak için Ctrl+C yapabilirsiniz.[/white]",
            title="Ninova Multi-Notifier",
            border_style="green",
        )
    )

    # Başlangıçta bir kez kullanıcı tablosunu göster
    show_users_table()
    console.print()

    def _signal_handler(signum, _frame):
        graceful_shutdown(f"signal {signum}")

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)

    if bot:
        try:
            logger.info("[Bot] Webhook temizleniyor...")
            try:
                bot.remove_webhook(drop_pending_updates=True)
            except TypeError:
                # Older pytelegrambotapi versions do not support drop_pending_updates.
                bot.remove_webhook()
            time.sleep(2)  # Telegram sunucularının senkronize olması için kısa bir bekleme
        except Exception as e:
            logger.exception(f"Webhook temizleme hatası: {e}")

        _start_polling_thread()
        logger.info("[Bot] Telegram komut dinleyicisi başlatıldı.")

    try:
        # Session cleanup counter (cleanup every SESSION_CLEANUP_INTERVAL)
        checks_since_cleanup = 0
        checks_until_cleanup = SESSION_CLEANUP_INTERVAL // CHECK_INTERVAL

        while not SHUTDOWN_EVENT.is_set():
            if bot and (POLLING_THREAD is None or not POLLING_THREAD.is_alive()):
                logger.warning("[Bot] Polling thread durmuş, yeniden başlatılıyor...")
                _start_polling_thread()

            current_wait = CHECK_INTERVAL + random.randint(-30, 30)
            # Bekleme sırasında Live display
            users_count = len(load_all_users())  # Disk I/O'yu 1 kere yap
            with Live(console=console, refresh_per_second=LIVE_REFRESH_PER_SECOND) as live:
                for i in range(current_wait):
                    if SHUTDOWN_EVENT.is_set():
                        break
                    if i % LIVE_STATUS_UPDATE_EVERY_SECONDS == 0:
                        status = "⏳ Sonraki kontrol bekleniyor...\n"
                        status += f"📊 Kullanıcı sayısı: {users_count}\n"
                        status += f"⏰ Kalan süre: {current_wait - i} saniye\n"
                        # Son kontrol zamanını göster (sabit kıl)
                        last_check_display = LAST_CHECK_DISPLAY_TIME or "Henüz kontrol yok"
                        status += f"📅 Son kontrol: {last_check_display}"
                        live.update(
                            Panel.fit(
                                status,
                                title="🔄 Sistem Durumu",
                                border_style="blue",
                            )
                        )
                    time.sleep(1)
            if SHUTDOWN_EVENT.is_set():
                break
            # Live kapandıktan sonra kontrol yap. Her görev ayrı korunur: eskiden
            # herhangi birindeki exception ana döngüden çıkıp botu tamamen kapatıyordu.
            for periodic_task in (
                check_and_announce_sks_menu,
                check_ari24_updates,
                check_daily_bulletin,
                check_for_updates,
            ):
                if SHUTDOWN_EVENT.is_set():
                    break
                try:
                    periodic_task()
                except Exception as e:
                    logger.exception(f"Periyodik görev hatası ({periodic_task.__name__}): {e}")

            # Session cleanup (every SESSION_CLEANUP_INTERVAL seconds)
            checks_since_cleanup += 1
            if checks_since_cleanup >= checks_until_cleanup:
                try:
                    closed = cleanup_inactive_sessions()
                    cache_stats = get_cache_stats()
                    logger.info(
                        f"Cleanup done: {closed} sessions closed, "
                        f"cache size={cache_stats['entries']}/{cache_stats['max_entries']}"
                    )
                    checks_since_cleanup = 0
                except Exception as e:
                    logger.exception(f"Session cleanup failed: {e}")
    except KeyboardInterrupt:
        graceful_shutdown("keyboard interrupt")
    except Exception as e:
        from rich.traceback import Traceback

        console.print(Traceback())
        error_msg = f"Ana döngüde kritik hata: {e!s}\n{traceback.format_exc()}"
        emit_terminal_and_log(error_msg, level="critical")
        graceful_shutdown("critical error")
    finally:
        graceful_shutdown("main exit")
