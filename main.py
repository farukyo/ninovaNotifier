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

import common.error_tracker as error_tracker
from bot import bot, set_check_callback, update_last_check_time
from common.config import (
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
    save_all_users,
    sync_cache_to_disk,
)
from common.log_context import clear_log_context, set_log_context
from common.logging_setup import setup_logging
from common.utils import (
    decrypt_password,
    escape_html,
    get_file_icon,
    load_saved_grades,
    parse_turkish_date,
    save_grades,
    send_telegram_message,
)
from services.ari24.client import Ari24Client
from services.ninova import LoginFailedError, get_announcement_detail, get_grades
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
            state["notified_urls"] = list(notified_urls.union(new_urls))[-500:]  # Keep last 500

        # --- NEWS CHECK ---
        notified_news = set(state.get("notified_news", []))
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

                notified_news.add(item["link"])

            state["notified_news"] = list(notified_news)[-200:]  # Keep last 200

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


def _compare_course_data(
    current_data,
    saved_data,
    user_session,
    course_name,
    include_reminders=False,
    include_console_log=False,
    username="",
    changes_table=None,
):
    """
    Bir ders için mevcut ve kayıtlı veriyi karşılaştırıp değişiklik listesi üretir.

    :param current_data: Ninova'dan çekilen güncel ders verisi
    :param saved_data: Daha önce kaydedilmiş ders verisi
    :param user_session: requests.Session (duyuru detayı çekmek için)
    :param course_name: Ders adı
    :param include_reminders: Ödev hatırlatma kontrolü yapılsın mı
    :param include_console_log: Rich console'a log yazılsın mı
    :param username: Kullanıcı adı (console log için)
    :param changes_table: Rich Table nesnesi (console log için)
    :return: (sections_changes, change_descriptions, new_file_entries) tuple
        new_file_entries: list of (file_idx, file_name) for newly added files
    """
    if not isinstance(saved_data, dict):
        saved_data = {}

    current_grades = current_data.get("grades", {})
    current_assignments = current_data.get("assignments", [])
    current_files = current_data.get("files", [])
    current_announcements = current_data.get("announcements", [])

    saved_grades = saved_data.get("grades", {})
    saved_assignments = saved_data.get("assignments", [])
    saved_files = saved_data.get("files", [])
    saved_announcements = saved_data.get("announcements", [])

    sections_changes = []
    changes = []
    new_file_entries = []  # (file_idx, file_name) for newly added files

    # --- 1. NOT KONTROLÜ ---
    for key, entry in current_grades.items():
        new_val = entry["not"]
        e_key, e_new_val = escape_html(key), escape_html(new_val)

        if key not in saved_grades:
            not_msg = f"📝 <b>YENİ NOT:</b> {e_key} -> {e_new_val}"
            details = entry.get("detaylar", {})
            detail_lines = []
            if entry.get("agirlik"):
                detail_lines.append(f"Ağırlık: %{entry['agirlik']}")
            if "class_avg" in details:
                detail_lines.append(f"Sınıf Ort: {details['class_avg']}")
            if "std_dev" in details:
                detail_lines.append(f"Std. Sapma: {details['std_dev']}")
            if "student_count" in details:
                detail_lines.append(f"Kişi Sayısı: {details['student_count']}")
            if "rank" in details:
                detail_lines.append(f"Sıralama: {details['rank']}")
            if detail_lines:
                not_msg += "\n" + " | ".join(detail_lines)
            sections_changes.append(not_msg)
            changes.append(f"YENİ NOT: {key} -> {new_val}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📝 Yeni Not: {key} -> {new_val}")
        else:
            old_entry = saved_grades[key]
            old_val = (old_entry.get("not") if isinstance(old_entry, dict) else old_entry) or "?"
            if old_val != new_val:
                e_old_val = escape_html(old_val)
                upd_msg = f"🔄 <b>NOT GÜNCELLENDİ:</b> {e_key}\n{e_old_val} ➡️ {e_new_val}"
                details = entry.get("detaylar", {})
                detail_lines = []
                if entry.get("agirlik"):
                    detail_lines.append(f"Ağırlık: %{entry['agirlik']}")
                if "class_avg" in details:
                    detail_lines.append(f"Ort: {details['class_avg']}")
                if "rank" in details:
                    detail_lines.append(f"Sıra: {details['rank']}")
                if detail_lines:
                    upd_msg += "\n" + " | ".join(detail_lines)
                sections_changes.append(upd_msg)
                changes.append(f"NOT GÜNCELLENDİ: {key} ({old_val} -> {new_val})")
                if include_console_log and changes_table:
                    changes_table.add_row(
                        username, course_name, f"🔄 Not Güncellendi: {key} ({old_val} -> {new_val})"
                    )

    # --- 2. ÖDEV KONTROLÜ & HATIRLATMA ---
    for assign in current_assignments:
        saved_assign = next((a for a in saved_assignments if a.get("id") == assign.get("id")), None)
        e_assign_name = escape_html(assign["name"])

        if not saved_assign:
            sections_changes.append(
                f"📅 <b>YENİ ÖDEV:</b> <a href='{assign['url']}'>{e_assign_name}</a>\n"
                f"Son Teslim: {assign['end_date']}"
            )
            changes.append(f"YENİ ÖDEV: {assign['name']}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📄 Yeni Ödev: {assign['name']}")
        else:
            if assign["end_date"] != saved_assign.get("end_date"):
                sections_changes.append(
                    f"🕒 <b>TESLİM TARİHİ DEĞİŞTİ:</b> {e_assign_name}\n"
                    f"Yeni Tarih: {assign['end_date']}"
                )
                changes.append(f"ÖDEV TARİHİ DEĞİŞTİ: {assign['name']}")
                if include_console_log and changes_table:
                    changes_table.add_row(
                        username, course_name, f"🕒 Ödev Tarihi Değişti: {assign['name']}"
                    )

            # Teslim durumu değişti mi?
            old_status = saved_assign.get("is_submitted")
            new_status = assign.get("is_submitted")
            if old_status is not None and old_status != new_status:
                status_str = "✅ TESLİM EDİLDİ" if new_status else "❌ TESLİM GERİ ÇEKİLDİ"
                sections_changes.append(
                    f"🔄 <b>ÖDEV DURUMU GÜNCELLENDİ:</b> {e_assign_name}\nDurum: {status_str}"
                )
                changes.append(f"ÖDEV DURUMU DEĞİŞTİ: {assign['name']} ({status_str})")

        # Hatırlatma sistemi
        if include_reminders and not assign.get("is_submitted", False) and assign.get("end_date"):
            due_date = parse_turkish_date(assign["end_date"])
            if due_date:
                time_left = due_date - datetime.now()
                hours_left = time_left.total_seconds() / 3600
                sent_reminders = []
                if saved_assign and "reminders_sent" in saved_assign:
                    sent_reminders = saved_assign["reminders_sent"]
                elif saved_assign:
                    saved_assign["reminders_sent"] = []

                reminder_tag = None
                reminder_msg = ""
                if 0 < hours_left <= 3 and "3h" not in sent_reminders:
                    reminder_tag = "3h"
                    reminder_msg = f"🚨 <b>SON 3 SAAT!</b> ({e_assign_name})"
                elif 3 < hours_left <= 24 and "24h" not in sent_reminders:
                    reminder_tag = "24h"
                    reminder_msg = f"⏳ <b>SON 24 SAAT!</b> ({e_assign_name})"

                if reminder_tag:
                    sections_changes.append(
                        f"{reminder_msg}\nBitiş: {assign['end_date']}\n"
                        f"<a href='{assign['url']}'>Ödeve Git</a>"
                    )
                    changes.append(f"HATIRLATMA ({reminder_tag}): {assign['name']}")
                    assign["reminders_sent"] = [*sent_reminders, reminder_tag]
                else:
                    assign["reminders_sent"] = sent_reminders
            elif saved_assign:
                assign["reminders_sent"] = saved_assign.get("reminders_sent", [])

    # --- 3. DOSYA KONTROLÜ ---
    saved_file_map = {f.get("url"): f for f in saved_files}
    for file_idx, file in enumerate(current_files):
        f_url = file["url"]
        if f_url not in saved_file_map:
            file_name = file["name"]
            new_file_entries.append((file_idx, file_name))
            changes.append(f"YENİ DOSYA: {file_name}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📎 Yeni Dosya: {file_name}")
        else:
            saved_file = saved_file_map[f_url]
            name_changed = file["name"] != saved_file.get("name")
            date_changed = file["date"] != saved_file.get("date")
            if name_changed or date_changed:
                e_file_name = escape_html(file["name"])
                icon = get_file_icon(file["name"].split("/")[-1])
                change_type = "GÜNCELLENDİ" if date_changed else "ADI DEĞİŞTİ"
                sections_changes.append(
                    f"{icon} <b>DOSYA {change_type}:</b> <a href='{f_url}'>{e_file_name}</a>"
                )
                changes.append(f"DOSYA {change_type}: {file['name']}")

    # --- 4. DUYURU KONTROLÜ ---
    saved_ann_map = {a.get("id"): a for a in saved_announcements}
    current_ann_ids = {a.get("id") for a in current_announcements}

    for ann in current_announcements:
        ann_id = ann.get("id")
        e_ann_title = escape_html(ann["title"])
        e_ann_author = escape_html(ann.get("author", ""))

        if ann_id not in saved_ann_map:
            full_content = get_announcement_detail(user_session, ann["url"])
            ann["content"] = full_content
            ann_msg = f"📣 <b>YENİ DUYURU:</b> <a href='{ann['url']}'>{e_ann_title}</a>"
            if include_reminders and e_ann_author:
                ann_msg += f"\n👤 {e_ann_author} | 📅 {ann['date']}\n\n{full_content}"
            sections_changes.append(ann_msg)
            changes.append(f"YENİ DUYURU: {ann['title']}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📣 Yeni Duyuru: {ann['title']}")
        else:
            saved_ann = saved_ann_map[ann_id]
            changed = (
                ann["title"] != saved_ann.get("title")
                or ann.get("author") != saved_ann.get("author")
                or ann.get("date") != saved_ann.get("date")
            )
            if changed:
                full_content = get_announcement_detail(user_session, ann["url"])
                ann["content"] = full_content
                sections_changes.append(
                    f"🔄 <b>DUYURU GÜNCELLENDİ:</b> <a href='{ann['url']}'>{e_ann_title}</a>"
                    f"\n👤 {e_ann_author} | 📅 {ann.get('date', '')}\n\n{full_content}"
                )
                changes.append(f"DUYURU GÜNCELLENDİ: {ann['title']}")
            else:
                ann["content"] = saved_ann.get("content", "")

    # --- 5. SİLİNMİŞ VERİLERİ KONTROL ET ---
    if current_data.get("fetch_success", True):
        current_grade_keys = set(current_grades.keys())
        for saved_key in saved_grades:
            if saved_key not in current_grade_keys:
                e_saved_key = escape_html(saved_key)
                sections_changes.append(f"🗑️ <b>NOT SİLİNDİ:</b> {e_saved_key}")
                changes.append(f"NOT SİLİNDİ: {saved_key}")

        current_assign_ids = {a.get("id") for a in current_assignments}
        for sa in saved_assignments:
            if sa.get("id") not in current_assign_ids:
                e_name = escape_html(sa.get("name", "Bilinmeyen Ödev"))
                sections_changes.append(f"🗑️ <b>ÖDEV SİLİNDİ:</b> {e_name}")
                changes.append(f"ÖDEV SİLİNDİ: {sa.get('name')}")

        current_file_urls = {f.get("url") for f in current_files}
        for sf in saved_files:
            if sf.get("url") not in current_file_urls:
                e_name = escape_html(sf.get("name", "Bilinmeyen Dosya"))
                icon = get_file_icon(sf.get("name", "").split("/")[-1])
                sections_changes.append(f"{icon} <b>DOSYA SİLİNDİ:</b> {e_name}")
                changes.append(f"DOSYA SİLİNDİ: {sf.get('name')}")

        for s_ann_id, s_ann in saved_ann_map.items():
            if s_ann_id not in current_ann_ids:
                e_title = escape_html(s_ann.get("title", "Bilinmeyen Duyuru"))
                sections_changes.append(f"🗑️ <b>DUYURU SİLİNDİ:</b> {e_title}")
                changes.append(f"DUYURU SİLİNDİ: {s_ann.get('title')}")

    return sections_changes, changes, new_file_entries


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
    :param silent: (Opsiyonel) Bildirim göndermeden sadece verileri güncelle (True/False)
    :return: Başarı durumu ve mesaj içeren dict
    """
    request_id = request_id or f"chk-{chat_id}-{int(time.time())}"
    set_log_context(chat_id=str(chat_id), action="check_user_updates", request_id=request_id)
    users = load_all_users()
    user_data = users.get(chat_id)
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
        clear_log_context()
        return {"success": False, "message": "Kullanıcı bilgileri bulunamadı."}

    # Son kontrol zamanını güncelle
    user_data["last_check"] = datetime.now().isoformat()
    all_urls = user_data.get("urls", [])

    if not all_urls:
        logger.warning(
            "[user] actor=%s | action=check_user_updates | status=no_courses | request_id=%s",
            chat_id,
            request_id,
        )
        clear_log_context()
        return {"success": False, "message": "Takip edilen ders bulunamadı."}

    # Eğer tek bir ders istenmişse filtrele
    if course_idx is not None:
        if course_idx < 0 or course_idx >= len(all_urls):
            logger.warning(
                "[user] actor=%s | action=check_user_updates | status=invalid_course_idx | request_id=%s",
                chat_id,
                request_id,
            )
            clear_log_context()
            return {"success": False, "message": "Geçersiz ders indeksi."}
        urls_to_scan = [all_urls[course_idx]]
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
        clear_log_context()
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
        clear_log_context()
        return {"success": False, "message": "Şifre çözme hatası."}

    saved_grades = load_saved_grades()
    user_saved_grades = saved_grades.get(chat_id, {})

    # Get user session (managed by SessionManager)
    user_session = get_user_session(chat_id)
    all_current_grades = {}
    all_changes = []
    telegram_messages = []

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
                grades = get_grades(user_session, url, chat_id, username, password)
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
                clear_log_context()
                return {"success": False, "message": "Ninova bağlantı hatası."}

            progress.update(task, advance=1)
            time.sleep(0.2)

    # Değişiklikleri kontrol et — ortak fonksiyon kullan
    new_file_notifications = []  # (course_url, course_name, file_idx, file_name)

    for url, current_data in all_current_grades.items():
        course_name = current_data.get("course_name", "Bilinmeyen Ders")
        saved_data = user_saved_grades.get(url, {})
        e_course = escape_html(course_name)

        sections_changes, changes, new_file_entries = _compare_course_data(
            current_data, saved_data, user_session, course_name
        )

        all_changes.extend(changes)

        for file_idx, file_name in new_file_entries:
            new_file_notifications.append((url, course_name, file_idx, file_name))

        if sections_changes and not silent:
            msg = f"📚 <b>{e_course}</b>\n\n" + "\n\n".join(sections_changes)
            telegram_messages.append(msg)

        # Kaydet
        user_saved_grades[url] = {
            "course_name": course_name,
            "grades": current_data.get("grades", {}),
            "assignments": current_data.get("assignments", []),
            "files": current_data.get("files", []),
            "announcements": current_data.get("announcements", []),
        }

    # Başarılı veri çekimi - hata sayacını sıfırla
    if all_current_grades:
        last_url = next(iter(all_current_grades.keys()), None)
        error_tracker.record_success(chat_id, username, last_url=last_url)

    # Verileri kaydet
    if all_changes:
        saved_grades[chat_id] = user_saved_grades
        save_grades(saved_grades)
        urls_list = list(user_saved_grades.keys())
        for t_msg in telegram_messages:
            send_telegram_message(chat_id, t_msg)
            time.sleep(1)
        if not silent and new_file_notifications:
            from telebot import types as tg_types

            for course_url, file_course_name, file_idx, file_name in new_file_notifications:
                try:
                    url_idx = urls_list.index(course_url)
                except ValueError:
                    continue
                basename = file_name.split("/")[-1]
                icon = get_file_icon(basename)
                markup = tg_types.InlineKeyboardMarkup()
                markup.add(
                    tg_types.InlineKeyboardButton(
                        "📥 İndir", callback_data=f"dl_{url_idx}_{file_idx}"
                    )
                )
                text = (
                    f"📚 <b>{escape_html(file_course_name)}</b>\n"
                    f"{icon} <b>YENİ DOSYA:</b> {escape_html(basename)}"
                )
                try:
                    bot.send_message(
                        chat_id,
                        text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(f"File notification send error for {chat_id}: {e}")
                time.sleep(1)

    # Kullanıcı verilerini kaydet
    save_all_users(users)

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
    clear_log_context()
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
    """
    update_last_check_time()
    msg = f"Kontrol Başlatıldı - {len(load_all_users())} kullanıcı"
    logger.info(msg)
    console.rule(f"[bold cyan][{time.strftime('%H:%M:%S')}] {msg}")

    # Değişiklikler tablosu
    changes_table = Table(title="🔄 Bu Kontrol Dönemindeki Değişiklikler")
    changes_table.add_column("Kullanıcı", style="bold blue", no_wrap=True)
    changes_table.add_column("Ders", style="bold green")
    changes_table.add_column("Değişiklik", style="yellow")

    users = load_all_users()
    saved_grades = load_saved_grades()
    changed_usernames = set()
    total_changes_count = 0

    for chat_id, user_data in users.items():
        request_id = f"auto-{chat_id}-{int(time.time())}"
        set_log_context(chat_id=str(chat_id), action="check_for_updates", request_id=request_id)
        # Son kontrol zamanını güncelle
        user_data["last_check"] = datetime.now().isoformat()
        urls = user_data.get("urls", [])
        if not urls:
            clear_log_context()
            continue

        username = user_data.get("username")
        encrypted_password = user_data.get("password")

        if not username or not encrypted_password:
            logger.warning(f"Kullanıcı bilgileri eksik ({chat_id}), pas geçiliyor.")
            clear_log_context()
            continue

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
            clear_log_context()
            continue

        if SHOW_VERBOSE_TERMINAL:
            console.print(f"[bold cyan]Kullanıcı kontrol ediliyor: {chat_id}")

        # Get user session (managed by SessionManager)
        user_session = get_user_session(chat_id)

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
                    executor.submit(get_grades, user_session, url, chat_id, username, password): url
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
                            logger.debug(
                                "[%s] %s - Login error on %s: %s", chat_id, username, url, e
                            )
                    except Exception as e:
                        logger.error(f"[{chat_id}] Ders tarama hatası ({url}): {e}")
                    finally:
                        progress.update(task, advance=1)

        user_saved_grades = saved_grades.get(chat_id, {})
        all_changes = []
        telegram_messages = []

        # Başarılı veri çekimi → hata sayacını sıfırla, düzeldi mesajı gönder
        if all_current_grades:
            last_url = next(iter(all_current_grades.keys()), None)
            error_tracker.record_success(chat_id, username, last_url=last_url)

        # Ortak fonksiyon ile değişiklikleri kontrol et
        new_file_notifications = []  # (course_url, course_name, file_idx, file_name)
        for url, current_data in all_current_grades.items():
            course_name = current_data.get("course_name", "Bilinmeyen Ders")
            saved_data = user_saved_grades.get(url, {})
            e_course = escape_html(course_name)

            sections_changes, changes, new_file_entries = _compare_course_data(
                current_data,
                saved_data,
                user_session,
                course_name,
                include_reminders=True,
                include_console_log=True,
                username=username,
                changes_table=changes_table,
            )

            all_changes.extend(changes)

            for file_idx, file_name in new_file_entries:
                new_file_notifications.append((url, course_name, file_idx, file_name))

            if sections_changes:
                msg = f"📚 <b>{e_course}</b>\n\n" + "\n\n".join(sections_changes)
                telegram_messages.append(msg)

            # Kaydet
            user_saved_grades[url] = {
                "course_name": course_name,
                "grades": current_data.get("grades", {}),
                "assignments": current_data.get("assignments", []),
                "files": current_data.get("files", []),
                "announcements": current_data.get("announcements", []),
            }

        if all_changes:
            logger.info(f"Değişiklik tespit edildi: {chat_id} - {len(all_changes)} öğe")
            changed_usernames.add(username or str(chat_id))
            total_changes_count += len(all_changes)
            if SHOW_VERBOSE_TERMINAL:
                console.print(
                    Panel(
                        "\n".join(all_changes),
                        title=f"[bold magenta]DEĞİŞİKLİK ({chat_id})",
                        border_style="magenta",
                    )
                )
            for t_msg in telegram_messages:
                send_telegram_message(chat_id, t_msg)
                time.sleep(1)

            saved_grades[chat_id] = user_saved_grades
            save_grades(saved_grades)

            if new_file_notifications:
                from telebot import types as tg_types

                urls_list = list(user_saved_grades.keys())
                for course_url, file_course_name, file_idx, file_name in new_file_notifications:
                    try:
                        url_idx = urls_list.index(course_url)
                    except ValueError:
                        continue
                    basename = file_name.split("/")[-1]
                    icon = get_file_icon(basename)
                    markup = tg_types.InlineKeyboardMarkup()
                    markup.add(
                        tg_types.InlineKeyboardButton(
                            "📥 İndir", callback_data=f"dl_{url_idx}_{file_idx}"
                        )
                    )
                    text = (
                        f"📚 <b>{escape_html(file_course_name)}</b>\n"
                        f"{icon} <b>YENİ DOSYA:</b> {escape_html(basename)}"
                    )
                    try:
                        bot.send_message(
                            chat_id,
                            text,
                            reply_markup=markup,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.error(f"File notification send error for {chat_id}: {e}")
                    time.sleep(1)

                clear_log_context()
        elif SHOW_VERBOSE_TERMINAL:
            console.print(f"[dim]Değişiklik yok ({chat_id})")

    logger.info("Kontrol tamamlandı.")

    # Kullanıcı verilerini kaydet (last_check güncellemeleri için)
    save_all_users(users)
    logger.info("Veriler kaydedildi.")

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
            # Live kapandıktan sonra kontrol yap
            check_and_announce_sks_menu()
            check_ari24_updates()
            check_daily_bulletin()
            check_for_updates()

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
