import time
import logging
import requests
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from common.config import console, load_all_users, HEADERS, USER_SESSIONS
from common.utils import (
    load_saved_grades,
    save_grades,
    send_telegram_message,
    escape_html,
    get_file_icon,
    decrypt_password,
)
from .scraper import (
    get_grades,
    get_announcement_detail,
)
from .auth import LoginFailedError, login_to_ninova
from bot import update_last_check_time

logger = logging.getLogger("ninova")


def check_for_updates():
    """
    Tüm kullanıcılar için ders verilerini tarar ve güncellemeleri kontrol eder.
    Yeni not, duyuru veya dosya varsa bildirim gönderir.
    """
    update_last_check_time()
    msg = f"Kontrol Başlatıldı - {len(load_all_users())} kullanıcı"
    logger.info(msg)
    console.rule(f"[bold cyan][{time.strftime('%H:%M:%S')}] {msg}")

    users = load_all_users()
    saved_grades = load_saved_grades()

    for chat_id, user_data in users.items():
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

        if chat_id not in USER_SESSIONS:
            USER_SESSIONS[chat_id] = requests.Session()
            USER_SESSIONS[chat_id].headers.update(HEADERS)
            console.print(f"[cyan][{chat_id}] Yeni oturum başlatılıyor...")
            if not login_to_ninova(
                USER_SESSIONS[chat_id], chat_id, username, password, quiet=True
            ):
                console.print(f"[bold red][{chat_id}] İlk giriş başarısız oldu!")
                continue

        user_session = USER_SESSIONS[chat_id]
        all_current_grades = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"[yellow]{chat_id} taranıyor...", total=len(urls))
            for url in urls:
                # URL'den suffix'leri temizle (eski format desteği)
                base_url = url
                for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari"]:
                    if base_url.endswith(suffix):
                        base_url = base_url[: -len(suffix)]
                        break
                try:
                    grades = get_grades(
                        user_session, base_url, chat_id, username, password
                    )
                    if grades:
                        all_current_grades[base_url] = grades
                except LoginFailedError:
                    error_msg = "⚠️ <b>Giriş Başarısız!</b>\n\nNinova'ya giriş yapılamıyor (Oturum hatası). Kontrol şu an için durduruldu."
                    console.print(
                        f"[bold red]Oturum açma hatası ({chat_id})! Diğer dersler atlanıyor."
                    )
                    send_telegram_message(chat_id, error_msg, is_error=True)
                    break

                progress.update(task, advance=1)
                time.sleep(0.2)

        if not all_current_grades:
            continue

        user_saved_grades = saved_grades.get(chat_id, {})
        changes = []
        telegram_messages = []

        for url, current_data in all_current_grades.items():
            course_name = current_data.get("course_name", "Bilinmeyen Ders")
            current_course_grades = current_data.get("grades", {})
            current_assignments = current_data.get("assignments", [])
            current_files = current_data.get("files", [])
            current_announcements = current_data.get("announcements", [])

            saved_data = user_saved_grades.get(url, {})
            if not isinstance(saved_data, dict):
                saved_data = {}

            saved_course_grades = saved_data.get("grades", {})
            saved_assignments = saved_data.get("assignments", [])
            saved_files = saved_data.get("files", [])
            saved_announcements = saved_data.get("announcements", [])

            e_course = escape_html(course_name)
            sections_changes = []

            # Not Kontrolü
            for key, entry in current_course_grades.items():
                new_val = entry["not"]
                if key not in saved_course_grades:
                    sections_changes.append(
                        f"📝 <b>YENİ NOT:</b> {escape_html(key)} -> {escape_html(new_val)}"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ NOT: {key} -> {new_val}"
                    )
                else:
                    old_val = (
                        saved_course_grades[key].get("not", "?")
                        if isinstance(saved_course_grades[key], dict)
                        else saved_course_grades[key]
                    )
                    if old_val != new_val:
                        sections_changes.append(
                            f"🔄 <b>NOT GÜNCELLENDİ:</b> {escape_html(key)}\n{escape_html(old_val)} ➡️ {escape_html(new_val)}"
                        )
                        changes.append(
                            f"[bold yellow][{course_name}] GÜNCELLENDİ: {key} ({old_val} -> {new_val})"
                        )

            # Ödev Kontrolü
            for assign in current_assignments:
                saved_assign = next(
                    (a for a in saved_assignments if a.get("id") == assign.get("id")),
                    None,
                )
                if not saved_assign:
                    sections_changes.append(
                        f"📅 <b>YENİ ÖDEV:</b> <a href='{assign['url']}'>{escape_html(assign['name'])}</a>\nSon Teslim: {assign['end_date']}"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ ÖDEV: {assign['name']}"
                    )
                else:
                    if assign["end_date"] != saved_assign.get("end_date"):
                        sections_changes.append(
                            f"🕒 <b>TESLİM TARİHİ DEĞİŞTİ:</b> {escape_html(assign['name'])}\nYeni Tarih: {assign['end_date']}"
                        )
                    if saved_assign.get("is_submitted") != assign.get("is_submitted"):
                        status_str = (
                            "✅ TESLİMEDİLDİ"
                            if assign.get("is_submitted")
                            else "❌ TESLİM GERİ ÇEKİLDİ"
                        )
                        sections_changes.append(
                            f"🔄 <b>ÖDEV DURUMU GÜNCELLENDİ:</b> {escape_html(assign['name'])}\nDurum: {status_str}"
                        )

            # Dosya Kontrolü
            saved_file_map = {f.get("url"): f for f in saved_files}
            for file in current_files:
                if file["url"] not in saved_file_map:
                    sections_changes.append(
                        f"{get_file_icon(file['name'])} <b>YENİ DOSYA:</b> <a href='{file['url']}'>{escape_html(file['name'])}</a>"
                    )
                    changes.append(
                        f"[bold green][{course_name}] YENİ DOSYA: {file['name']}"
                    )

            # Duyuru Kontrolü
            saved_ann_map = {a.get("id"): a for a in saved_announcements}
            for ann in current_announcements:
                ann_id = ann.get("id")
                if ann_id not in saved_ann_map:
                    full_content = get_announcement_detail(user_session, ann["url"])
                    ann["content"] = full_content
                    sections_changes.append(
                        f"📣 <b>YENİ DUYURU:</b> <a href='{ann['url']}'>{escape_html(ann['title'])}</a>\n👤 {escape_html(ann['author'])} | 📅 {ann['date']}\n\n{escape_html(full_content)}"
                    )
                else:
                    ann["content"] = saved_ann_map[ann_id].get("content", "")

            if sections_changes:
                msg = f"📢 <b>{e_course}</b>\n\n" + "\n\n".join(sections_changes)
                telegram_messages.append(msg)

            user_saved_grades[url] = {
                "course_name": course_name,
                "grades": current_course_grades,
                "assignments": current_assignments,
                "files": current_files,
                "announcements": current_announcements,
            }

        if changes:
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
