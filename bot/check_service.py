"""Ninova değişiklik kontrolü: tarama, karşılaştırma, kayıt ve bildirim akışı.

Hem ana döngü (check_for_updates) hem de Telegram handler'ları (check_user_updates)
buradan kullanır. Eskiden bu kod main.py'deydi ve handler'lar ona
sys.modules["__main__"] üzerinden erişiyordu; bu, main.py'nin ikinci kez import
edilip kilitlerin/global durumun ikiye bölünmesine yol açabiliyordu.

migrated from: main.py
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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
from bot.callback_parsing import url_token
from bot.instance import bot_instance as bot
from bot.instance import update_last_check_time
from core.config import (
    console,
    get_user_session,
    load_all_users,
)
from core.logger import clear_log_context, set_log_context
from core.storage import modify_user, update_user_grades
from core.utils import (
    decrypt_password,
    escape_html,
    get_file_icon,
    load_saved_grades,
    send_telegram_message,
)
from services.ninova import (
    LoginFailedError,
    get_grades,
    login_to_ninova,
)
from services.ninova.diff_engine import compare_course_data

logger = logging.getLogger("ninova")

# Son kontrol zamanı - main.py'deki Live ekranı bunu gösterir
LAST_CHECK_DISPLAY_TIME = None

# Terminal çıktı ayarı (gürültüyü azaltmak için)
SHOW_VERBOSE_TERMINAL = False

# Kapanış sinyali: main.py set eder, uzun süren genel kontrol kullanıcılar arasında durur.
SHUTDOWN_EVENT = threading.Event()

# Aynı anda iki genel kontrol (ana döngü + admin "force") veya aynı kullanıcı için iki
# kontrol (otomatik + manuel) çalışırsa ikisi de aynı kayıtlı veriye göre fark hesaplayıp
# aynı bildirimi iki kez gönderiyor, sonra birbirinin kaydını eziyordu.
_GLOBAL_CHECK_LOCK = threading.Lock()
_USER_CHECK_LOCKS: dict[str, threading.Lock] = {}
_USER_CHECK_LOCKS_GUARD = threading.Lock()


def _user_check_lock(chat_id: str) -> threading.Lock:
    with _USER_CHECK_LOCKS_GUARD:
        return _USER_CHECK_LOCKS.setdefault(str(chat_id), threading.Lock())


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
