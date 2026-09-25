import json
import logging
import random
import signal
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.table import Table

import bot.check_service as check_service
import core.error_tracker as error_tracker
from bot import bot, set_check_callback
from bot.check_service import SHUTDOWN_EVENT, check_for_updates, emit_terminal_and_log
from core.config import (
    CHECK_INTERVAL,
    DATA_DIR,
    LOGS_DIR,
    SESSION_CLEANUP_INTERVAL,
    atomic_json_write,
    cleanup_inactive_sessions,
    console,
    get_cache_stats,
    load_all_users,
    sync_cache_to_disk,
)
from core.logger import install_thread_excepthook, setup_logging
from core.utils import escape_attr, escape_html
from services.ari24.client import Ari24Client
from services.sks.announcer import check_and_announce_sks_menu

# Logging yapılandırması
_logs_dir = Path(LOGS_DIR)
_log_handler = setup_logging(_logs_dir)
install_thread_excepthook()


logger = logging.getLogger("ninova")


# Terminal çıktı ayarları (gürültüyü azaltmak için)
LIVE_REFRESH_PER_SECOND = 0.5
LIVE_STATUS_UPDATE_EVERY_SECONDS = 10
POLLING_TIMEOUT_SECONDS = 20
POLLING_LONG_TIMEOUT_SECONDS = 20
POLLING_LOG_LEVEL = logging.WARNING
POLLING_THREAD: threading.Thread | None = None
_SHUTDOWN_LOCK = threading.Lock()


# error_tracker: yükle ve artık var olmayan kullanıcıları temizle
error_tracker.load(known_user_ids=set(load_all_users().keys()))
_SHUTDOWN_DONE = False


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


def _run_polling() -> None:
    """
    Telegram polling'i çalıştırır; hata alırsa bekleyip yeniden dener.

    infinity_polling, başlangıçta bekleyen güncellemeleri atlarken (skip_pending) ağ
    hatası alırsa exception'ı yakalamıyor ve thread ölüyordu; ana döngü bunu ancak bir
    sonraki turda (~5 dk) fark ediyor, bot bu sürede hiçbir mesaja yanıt vermiyordu.
    """
    skip_pending = True
    while not SHUTDOWN_EVENT.is_set():
        try:
            bot.infinity_polling(
                skip_pending=skip_pending,
                timeout=POLLING_TIMEOUT_SECONDS,
                long_polling_timeout=POLLING_LONG_TIMEOUT_SECONDS,
                logger_level=POLLING_LOG_LEVEL,
            )
            return  # stop_polling() çağrıldı
        except Exception as e:
            logger.error(f"Telegram polling hatası, 10 sn sonra yeniden denenecek: {e}")
            # Kesinti sırasında gelen mesajlar yeniden denemede atlanmasın.
            skip_pending = False
            SHUTDOWN_EVENT.wait(10)


def _start_polling_thread() -> None:
    """Start Telegram polling in a daemon thread with resilient defaults."""
    global POLLING_THREAD
    POLLING_THREAD = threading.Thread(target=_run_polling, name="telegram-polling", daemon=True)
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
                        f"🔔 <b>Yeni Etkinlik: {escape_html(club)}</b>\n\n"
                        f"📅 <b>{escape_html(event['title'])}</b>\n"
                        f"🕒 {escape_html(event['date_str'])}\n"
                        f"🔗 <a href='{escape_attr(url)}'>Detaylar</a>"
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
                    f"📰 <b>Yeni Haber: {escape_html(item['title'])}</b>\n"
                    f"🔗 <a href='{escape_attr(item['link'])}'>Haberi Oku</a>"
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
                    f"▫️ {escape_html(ev['organizer'])} - {escape_html(ev['title'])}\n"
                    f"⏰ {escape_html(ev['date_str'])}\n"
                    f"🔗 <a href='{escape_attr(ev['link'])}'>İncele</a>\n\n"
                )
        else:
            bulletin_message += "📅 <b>BUGÜN:</b>\n<i>Etkinlik bulunmuyor.</i>\n\n"

        if upcoming_events:
            bulletin_message += "🗓 <b>YAKLAŞANLAR (Bu hafta + Gelecek Hafta):</b>\n"
            # Maybe limit upcoming to avoid huge messages?
            # Limit to 10 upcoming events
            for ev in upcoming_events[:15]:
                bulletin_message += (
                    f"▫️ {escape_html(ev['date_str'])} | {escape_html(ev['organizer'])}\n"
                    f"   <b>{escape_html(ev['title'])}</b>\n\n"
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
                        last_check_display = (
                            check_service.LAST_CHECK_DISPLAY_TIME or "Henüz kontrol yok"
                        )
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
