import time
import random
import threading
import traceback
import requests
import logging
from datetime import datetime
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from core.config import (
    CHECK_INTERVAL,
    console,
    load_all_users,
    HEADERS,
    USER_SESSIONS,
    LOGS_DIR,
)
from core.utils import (
    load_saved_grades,
    save_grades,
    send_telegram_message,
    escape_html,
    parse_turkish_date,
    get_file_icon,
    decrypt_password,
)
from ninova import get_grades, get_announcement_detail, LoginFailedError
from core.logic import predict_course_performance
from bot import bot, set_check_callback, update_last_check_time

# Logging yapılandırması - Sadece dosyaya
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(os.path.join(LOGS_DIR, "app.log"), encoding="utf-8")],
)
logger = logging.getLogger("ninova")

# Son kontrol zamanı (global) - Live display'de kullanılacak
LAST_CHECK_DISPLAY_TIME = None


def show_users_table():
    """Kayıtlı kullanıcıları tablo formatında gösterir."""
    users = load_all_users()
    if not users:
        console.print("[yellow]Henüz kayıtlı kullanıcı yok.[/yellow]")
        return

    table = Table(
        title="📋 Kayıtlı Kullanıcılar", show_header=True, header_style="bold magenta"
    )
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


def check_user_updates(chat_id: str):
    """Belirli bir kullanıcının notlarını kontrol eder (Bot /kontrol komutu için)."""
    users = load_all_users()
    user_data = users.get(chat_id)

    if not user_data:
        return {"success": False, "message": "Kullanıcı bilgileri bulunamadı."}

    # Son kontrol zamanını güncelle
    user_data["last_check"] = datetime.now().isoformat()
    urls = user_data.get("urls", [])

    if not urls:
        return {"success": False, "message": "Takip edilen ders bulunamadı."}

    username = user_data.get("username")
    encrypted_password = user_data.get("password")

    if not username or not encrypted_password:
        return {"success": False, "message": "Kullanıcı bilgileri eksik."}

    password = decrypt_password(encrypted_password)
    saved_grades = load_saved_grades()
    user_saved_grades = saved_grades.get(chat_id, {})

    # Oturum önbelleğini kontrol et
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = requests.Session()
        USER_SESSIONS[chat_id].headers.update(HEADERS)

    user_session = USER_SESSIONS[chat_id]
    all_current_grades = {}
    changes = []
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
        task = progress.add_task(
            f"[yellow]{username} ({len(urls)} ders) taranıyor...", total=len(urls)
        )
        for url in urls:
            try:
                grades = get_grades(user_session, url, chat_id, username, password)
                if grades:
                    all_current_grades[url] = grades
            except LoginFailedError:
                error_msg = "⚠️ <b>Giriş Başarısız!</b>\n\nNinova'ya giriş yapılamıyor (Oturum hatası)."
                send_telegram_message(chat_id, error_msg, is_error=True)
                return {"success": False, "message": f"Oturum açma hatası: {error_msg}"}

            progress.update(task, advance=1)
            time.sleep(0.2)

    # Değişiklikleri kontrol et
    for url, current_data in all_current_grades.items():
        course_name = current_data.get("course_name", "Bilinmeyen Ders")
        current_course_grades = current_data.get("grades", {})
        current_assignments = current_data.get("assignments", [])
        current_files = current_data.get("files", [])

        saved_data = user_saved_grades.get(url, {})
        if not isinstance(saved_data, dict):
            saved_data = {}

        saved_course_grades = saved_data.get("grades", {})
        saved_assignments = saved_data.get("assignments", [])
        saved_files = saved_data.get("files", [])

        e_course = escape_html(course_name)
        sections_changes = []

        # NOT KONTROLÜ
        for key, entry in current_course_grades.items():
            new_val = entry["not"]
            e_key, e_new_val = escape_html(key), escape_html(new_val)

            if key not in saved_course_grades:
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
            else:
                old_entry = saved_course_grades[key]
                old_val = (
                    old_entry.get("not")
                    if isinstance(old_entry, dict)
                    else old_entry
                ) or "?"
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

        # ÖDEV KONTROLÜ
        for assign in current_assignments:
            saved_assign = next(
                (a for a in saved_assignments if a.get("id") == assign.get("id")),
                None,
            )
            e_assign_name = escape_html(assign["name"])

            if not saved_assign:
                sections_changes.append(
                    f"📅 <b>YENİ ÖDEV:</b> <a href='{assign['url']}'>{e_assign_name}</a>\n"
                    f"Son Teslim: {assign['end_date']}"
                )
                changes.append(f"YENİ ÖDEV: {assign['name']}")
            else:
                if assign["end_date"] != saved_assign.get("end_date"):
                    sections_changes.append(
                        f"🕒 <b>TESLİM TARİHİ DEĞİŞTİ:</b> {e_assign_name}\n"
                        f"Yeni Tarih: {assign['end_date']}"
                    )
                    changes.append(f"ÖDEV TARİHİ DEĞİŞTİ: {assign['name']}")

        # DOSYA KONTROLÜ
        saved_file_map = {f.get("url"): f for f in saved_files}
        for file in current_files:
            f_url = file["url"]
            if f_url not in saved_file_map:
                e_file_name = escape_html(file["name"])
                icon = get_file_icon(file["name"].split("/")[-1])
                sections_changes.append(
                    f"{icon} <b>YENİ DOSYA:</b> <a href='{f_url}'>{e_file_name}</a>"
                )
                changes.append(f"YENİ DOSYA: {file['name']}")

        # DUYURU KONTROLÜ
        current_announcements = current_data.get("announcements", [])
        saved_announcements = saved_data.get("announcements", [])
        saved_ann_map = {a.get("id"): a for a in saved_announcements}

        for ann in current_announcements:
            ann_id = ann.get("id")
            e_ann_title = escape_html(ann["title"])

            if ann_id not in saved_ann_map:
                full_content = get_announcement_detail(user_session, ann["url"])
                ann["content"] = full_content
                sections_changes.append(
                    f"📣 <b>YENİ DUYURU:</b> <a href='{ann['url']}'>{e_ann_title}</a>"
                )
                changes.append(f"YENİ DUYURU: {ann['title']}")

        # BİLDİRİM GÖNDERME
        if sections_changes:
            msg = f"📢 <b>{e_course}</b>\n\n" + "\n\n".join(sections_changes)
            if any("NOT" in s for s in sections_changes):
                perf = predict_course_performance(current_data)
                if perf and "current_avg" in perf:
                    msg += f"\n\n📈 <b>Ortalama:</b> <code>{perf['current_avg']:.2f}</code>"
                    if "predicted_letter" in perf:
                        msg += (
                            f" | <b>Tahmin:</b> <code>{perf['predicted_letter']}</code>"
                        )
            telegram_messages.append(msg)

        # KAYDETME
        new_saved_data = {
            "course_name": course_name,
            "grades": current_course_grades,
            "assignments": current_assignments,
            "files": current_files,
            "announcements": current_announcements,
        }
        user_saved_grades[url] = new_saved_data

    # Verileri kaydet
    if changes:
        saved_grades[chat_id] = user_saved_grades
        save_grades(saved_grades)
        for t_msg in telegram_messages:
            send_telegram_message(chat_id, t_msg)
            time.sleep(1)

    # Kullanıcı verilerini kaydet
    from core.config import save_all_users

    save_all_users(users)

    # Son kontrol zamanını güncelle
    global LAST_CHECK_DISPLAY_TIME
    LAST_CHECK_DISPLAY_TIME = datetime.now().strftime("%H:%M:%S")

    result_msg = f"✅ Kontrol tamamlandı ({len(changes)} değişiklik)"
    if not changes:
        result_msg = "✅ Kontrol tamamlandı (değişiklik yok)"

    return {"success": True, "message": result_msg, "changes": len(changes)}


def check_for_updates():
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

    for chat_id, user_data in users.items():
        # Son kontrol zamanını güncelle
        user_data["last_check"] = datetime.now().isoformat()
        urls = user_data.get("urls", [])
        if not urls:
            continue

        username = user_data.get("username")
        encrypted_password = user_data.get("password")

        if not username or not encrypted_password:
            console.print(
                f"[yellow]Kullanıcı bilgileri eksik ({chat_id}), pas geçiliyor."
            )
            continue

        password = decrypt_password(encrypted_password)

        console.print(f"[bold cyan]Kullanıcı kontrol ediliyor: {chat_id}")

        # Oturum önbelleğini kontrol et
        if chat_id not in USER_SESSIONS:
            USER_SESSIONS[chat_id] = requests.Session()
            USER_SESSIONS[chat_id].headers.update(HEADERS)

        user_session = USER_SESSIONS[chat_id]

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
                f"[yellow]{username} ({len(urls)} ders) taranıyor...", total=len(urls)
            )
            for url in urls:
                try:
                    grades = get_grades(user_session, url, chat_id, username, password)
                    if grades:
                        all_current_grades[url] = grades
                except LoginFailedError:
                    error_msg = "⚠️ <b>Giriş Başarısız!</b>\n\nNinova'ya giriş yapılamıyor (Oturum hatası). Kontrol şu an için durduruldu."
                    console.print(
                        f"[bold red]Oturum açma hatası ({chat_id})! Diğer dersler atlanıyor."
                    )
                    send_telegram_message(chat_id, error_msg, is_error=True)
                    break

                progress.update(task, advance=1)
                time.sleep(0.2)

        user_saved_grades = saved_grades.get(chat_id, {})
        changes = []
        telegram_messages = []

        for url, current_data in all_current_grades.items():
            course_name = current_data.get("course_name", "Bilinmeyen Ders")

            # Verileri al
            current_course_grades = current_data.get("grades", {})
            current_assignments = current_data.get("assignments", [])
            current_files = current_data.get("files", [])

            saved_data = user_saved_grades.get(url, {})
            if not isinstance(saved_data, dict):
                saved_data = {}

            saved_course_grades = saved_data.get("grades", {})
            saved_assignments = saved_data.get("assignments", [])
            saved_files = saved_data.get("files", [])

            e_course = escape_html(course_name)
            sections_changes = []

            # --- 1. NOT KONTROLÜ ---
            for key, entry in current_course_grades.items():
                new_val = entry["not"]
                e_key, e_new_val = escape_html(key), escape_html(new_val)

                if key not in saved_course_grades:
                    # Yeni NOT mesajı
                    not_msg = f"📝 <b>YENİ NOT:</b> {e_key} -> {e_new_val}"

                    # Detayları ekle
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
                    changes.append(
                        f"[bold green][{course_name}] YENİ NOT: {key} -> {new_val}"
                    )
                    changes_table.add_row(
                        username, course_name, f"📝 Yeni Not: {key} -> {new_val}"
                    )
                else:
                    old_entry = saved_course_grades[key]
                    old_val = (
                        old_entry.get("not")
                        if isinstance(old_entry, dict)
                        else old_entry
                    ) or "?"

                    if old_val != new_val:
                        e_old_val = escape_html(old_val)

                        # Güncelleme mesajı
                        upd_msg = f"🔄 <b>NOT GÜNCELLENDİ:</b> {e_key}\n{e_old_val} ➡️ {e_new_val}"

                        # Detayları ekle
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
                        changes.append(
                            f"[bold yellow][{course_name}] GÜNCELLENDİ: {key} ({old_val} -> {new_val})"
                        )
                        changes_table.add_row(
                            username,
                            course_name,
                            f"🔄 Not Güncellendi: {key} ({old_val} -> {new_val})",
                        )

            # --- 2. ÖDEV KONTROLÜ & HATIRLATMA ---
            for assign in current_assignments:
                # Assign ID ile eşleştir
                saved_assign = next(
                    (a for a in saved_assignments if a.get("id") == assign.get("id")),
                    None,
                )
                e_assign_name = escape_html(assign["name"])

                if not saved_assign:
                    sections_changes.append(
                        f"📅 <b>YENİ ÖDEV:</b> <a href='{assign['url']}'>{e_assign_name}</a>\n"
                        f"Son Teslim: {assign['end_date']}"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ ÖDEV: {assign['name']}"
                    )
                    changes_table.add_row(
                        username, course_name, f"📄 Yeni Ödev: {assign['name']}"
                    )
                else:
                    # Tarih değişti mi?
                    if assign["end_date"] != saved_assign.get("end_date"):
                        sections_changes.append(
                            f"🕒 <b>TESLİM TARİHİ DEĞİŞTİ:</b> {e_assign_name}\n"
                            f"Yeni Tarih: {assign['end_date']}"
                        )
                        changes.append(
                            f"[bold yellow][{course_name}] ÖDEV TARİHİ DEĞİŞTİ: {assign['name']}"
                        )
                        changes_table.add_row(
                            username,
                            course_name,
                            f"🕒 Ödev Tarihi Değişti: {assign['name']}",
                        )

                    # Teslim durumu değişti mi? (Sadece eski veri varsa ve değişmişse)
                    old_status = saved_assign.get("is_submitted")
                    new_status = assign.get("is_submitted")
                    if old_status is not None and old_status != new_status:
                        status_str = (
                            "✅ TESLİMEDİLDİ"
                            if new_status
                            else "❌ TESLİM GERİ ÇEKİLDİ"
                        )
                        sections_changes.append(
                            f"🔄 <b>ÖDEV DURUMU GÜNCELLENDİ:</b> {e_assign_name}\nDurum: {status_str}"
                        )
                        changes.append(
                            f"[bold yellow][{course_name}] ÖDEV DURUMU DEĞİŞTİ: {assign['name']} ({status_str})"
                        )

                # [REMINDER LOGIC]
                # Sadece süresi dolmamış ve teslim edilmemiş ödevler için
                if not assign.get("is_submitted", False) and assign.get("end_date"):
                    due_date = parse_turkish_date(assign["end_date"])
                    if due_date:
                        time_left = due_date - datetime.now()
                        hours_left = time_left.total_seconds() / 3600

                        sent_reminders = []
                        if saved_assign and "reminders_sent" in saved_assign:
                            sent_reminders = saved_assign["reminders_sent"]
                        elif saved_assign:
                            saved_assign["reminders_sent"] = []
                            sent_reminders = []

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
                                f"{reminder_msg}\nBitiş: {assign['end_date']}\n<a href='{assign['url']}'>Ödeve Git</a>"
                            )
                            changes.append(
                                f"[bold magenta][{course_name}] HATIRLATMA ({reminder_tag}): {assign['name']}"
                            )
                            assign["reminders_sent"] = sent_reminders + [reminder_tag]
                        else:
                            assign["reminders_sent"] = sent_reminders
                    else:
                        if saved_assign:
                            assign["reminders_sent"] = saved_assign.get(
                                "reminders_sent", []
                            )

            # --- 3. DOSYA KONTROLÜ ---
            saved_file_map = {f.get("url"): f for f in saved_files}
            for file in current_files:
                f_url = file["url"]
                if f_url not in saved_file_map:
                    e_file_name = escape_html(file["name"])
                    icon = get_file_icon(file["name"].split("/")[-1])
                    sections_changes.append(
                        f"{icon} <b>YENİ DOSYA:</b> <a href='{f_url}'>{e_file_name}</a>"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ DOSYA: {file['name']}"
                    )
                    changes_table.add_row(
                        username, course_name, f"📎 Yeni Dosya: {file['name']}"
                    )
                else:
                    saved_file = saved_file_map[f_url]
                    # Dosya ismi veya tarihi değişti mi?
                    name_changed = file["name"] != saved_file.get("name")
                    date_changed = file["date"] != saved_file.get("date")

                    if name_changed or date_changed:
                        e_file_name = escape_html(file["name"])
                        icon = get_file_icon(file["name"].split("/")[-1])
                        change_type = "GÜNCELLENDİ" if date_changed else "ADI DEĞİŞTİ"

                        sections_changes.append(
                            f"{icon} <b>DOSYA {change_type}:</b> <a href='{f_url}'>{e_file_name}</a>"
                        )
                        changes.append(
                            f"[bold yellow][{course_name}] DOSYA {change_type}: {file['name']}"
                        )

            # --- 4. DUYURU KONTROLÜ ---
            current_announcements = current_data.get("announcements", [])
            saved_announcements = saved_data.get("announcements", [])
            saved_ann_map = {a.get("id"): a for a in saved_announcements}
            current_ann_ids = {a.get("id") for a in current_announcements}

            # Yeni ve Güncellenen Duyurular
            for ann in current_announcements:
                ann_id = ann.get("id")
                e_ann_title = escape_html(ann["title"])
                e_ann_author = escape_html(ann["author"])

                if ann_id not in saved_ann_map:
                    # Yeni Duyuru - Tam içeriği detay sayfasından çek
                    full_content = get_announcement_detail(user_session, ann["url"])
                    ann["content"] = full_content

                    sections_changes.append(
                        f"📣 <b>YENİ DUYURU:</b> <a href='{ann['url']}'>{e_ann_title}</a>\n"
                        f"👤 {e_ann_author} | 📅 {ann['date']}\n\n"
                        f"{escape_html(full_content)}"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ DUYURU: {ann['title']}"
                    )
                    changes_table.add_row(
                        username, course_name, f"📣 Yeni Duyuru: {ann['title']}"
                    )
                else:
                    # Güncellenmiş mi kontrol et (İçerik hariç, çünkü current'ta boş)
                    saved_ann = saved_ann_map[ann_id]
                    changed = (
                        ann["title"] != saved_ann.get("title")
                        or ann["author"] != saved_ann.get("author")
                        or ann["date"] != saved_ann.get("date")
                    )

                    if changed:
                        full_content = get_announcement_detail(user_session, ann["url"])
                        ann["content"] = full_content

                        sections_changes.append(
                            f"🔄 <b>DUYURU GÜNCELLENDİ:</b> <a href='{ann['url']}'>{e_ann_title}</a>\n"
                            f"👤 {e_ann_author} | 📅 {ann['date']}\n\n"
                            f"{escape_html(full_content)}"
                        )
                        changes.append(
                            f"[bold yellow][{course_name}] DUYURU GÜNCELLENDİ: {ann['title']}"
                        )
                    else:
                        # Önceki tam içeriği koru
                        ann["content"] = saved_ann.get("content", "")

            # Silinen Duyurular
            for s_ann_id, s_ann in saved_ann_map.items():
                if s_ann_id not in current_ann_ids:
                    e_ann_title = escape_html(s_ann.get("title", "Bilinmeyen Duyuru"))
                    sections_changes.append(f"🗑️ <b>DUYURU SİLİNDİ:</b> {e_ann_title}")
                    changes.append(
                        f"[bold red][{course_name}] DUYURU SİLİNDİ: {s_ann.get('title')}"
                    )

            # --- BİLDİRİM GÖNDERME ---
            if sections_changes:
                msg = f"📢 <b>{e_course}</b>\n\n" + "\n\n".join(sections_changes)
                # Not Performans Özeti (Sadece not değişikliği varsa ekleyelim)
                if any("NOT" in s for s in sections_changes):
                    perf = predict_course_performance(current_data)
                    if perf and "current_avg" in perf:
                        msg += f"\n\n📈 <b>Ortalama:</b> <code>{perf['current_avg']:.2f}</code>"
                        if "predicted_letter" in perf:
                            msg += f" | <b>Tahmin:</b> <code>{perf['predicted_letter']}</code>"

                telegram_messages.append(msg)

            # --- KAYDETME ---
            new_saved_data = {
                "course_name": course_name,
                "grades": current_course_grades,
                "assignments": current_assignments,
                "files": current_files,
                "announcements": current_announcements,
            }
            user_saved_grades[url] = new_saved_data

        if changes:
            logger.info(f"Değişiklik tespit edildi: {chat_id} - {len(changes)} öğe")
            console.print(
                Panel(
                    "\n".join(changes),
                    title=f"[bold magenta]DEĞİŞİKLİK ({chat_id})",
                    border_style="magenta",
                )
            )
            for t_msg in telegram_messages:
                send_telegram_message(chat_id, t_msg)
                time.sleep(1)

            saved_grades[chat_id] = user_saved_grades
            save_grades(saved_grades)
        else:
            console.print(f"[dim]Değişiklik yok ({chat_id})")

    console.print("[italic white]Kontrol tamamlandı.")

    # Kullanıcı verilerini kaydet (last_check güncellemeleri için)
    from core.config import save_all_users

    save_all_users(users)
    console.print("[dim]Veriler kaydedildi.")

    # Değişiklikler tablosunu göster (eğer değişiklik varsa)
    if changes_table.rows:
        console.print()
        console.print(changes_table)
    else:
        console.print("[dim]Bu kontrol döneminde değişiklik yok.[/dim]")

    # Güncellenmiş kullanıcı tablosunu göster
    console.print()
    show_users_table()
    console.print("[green]✅ Kontrol tamamlandı - İçindekiler güncellenmiş.")

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

    # Kullanıcı tablosunu göster
    show_users_table()
    console.print()  # Boş satır

    if bot:
        try:
            console.print("[yellow][Bot] Webhook temizleniyor...")
            bot.remove_webhook(drop_pending_updates=True)
            time.sleep(
                2
            )  # Telegram sunucularının senkronize olması için kısa bir bekleme
        except Exception:
            pass

        # infinity_polling kendi içinde hata yönetimi yapar.
        # logger_level parametresi ile log kirliliğini azaltabiliriz.
        threading.Thread(
            target=bot.infinity_polling,
            kwargs={"skip_pending": True, "timeout": 20},
            daemon=True,
        ).start()
        console.print("[bold cyan][Bot] Telegram komut dinleyicisi başlatıldı.")

    try:
        while True:
            current_wait = CHECK_INTERVAL + random.randint(-30, 30)
            # Bekleme sırasında Live display
            users_count = len(load_all_users())  # Disk I/O'yu 1 kere yap
            with Live(console=console, refresh_per_second=1) as live:
                for i in range(current_wait):
                    if i % 5 == 0:  # Her 5 saniyede güncelle
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
            # Live kapandıktan sonra kontrol yap
            check_for_updates()
    except KeyboardInterrupt:
        console.print("\n[bold red]Program kullanıcı tarafından durduruldu.")
    except Exception as e:
        from rich.traceback import Traceback

        console.print(Traceback())
        error_msg = f"Ana döngüde kritik hata: {str(e)}\n{traceback.format_exc()}"
        console.print(f"[bold red]{error_msg}")
