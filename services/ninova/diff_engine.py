"""Ders verisi karşılaştırma (diff) motoru.

Ninova'dan çekilen güncel ders verisini kayıtlı veriyle karşılaştırır ve Telegram'a
gönderilecek değişiklik metinlerini üretir. Telegram'a veya depolamaya bağımlı değildir;
sadece yeni/güncellenen duyuruların tam metni için duyuru detay sayfasını çeker.

migrated from: main.py (_compare_course_data, _content_diff)
"""

from __future__ import annotations

import copy
import difflib
import logging
from datetime import datetime

from core.utils import escape_attr, escape_html, get_file_icon, parse_turkish_date

from .scraper import get_announcement_detail

logger = logging.getLogger("ninova")


def content_diff(old: str, new: str, context: int = 2) -> str:
    """Return a compact line-based diff with ➖/➕ prefixes for Telegram."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    result = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ctx = old_lines[i1:i2]
            if len(ctx) > context * 2:
                result += [f"  {line}" for line in ctx[:context]]
                result.append("  ...")
                result += [f"  {line}" for line in ctx[-context:]]
            else:
                result += [f"  {line}" for line in ctx]
        elif tag in ("replace", "delete"):
            result += [f"➖ {line}" for line in old_lines[i1:i2]]
            if tag == "replace":
                result += [f"➕ {line}" for line in new_lines[j1:j2]]
        elif tag == "insert":
            result += [f"➕ {line}" for line in new_lines[j1:j2]]
    return "\n".join(result)


def compare_course_data(
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
    :return: (sections_changes, change_descriptions, new_file_entries, updated_file_entries, assignment_source_entries) tuple
        new_file_entries: list of (file_idx, file_name) for newly added course files
        updated_file_entries: list of (file_idx, file_name, change_type) for updated course files
        assignment_source_entries: list of (assign_idx, sf_idx, file_name, file_size, assign_name, is_new_assign) for assignment source files
    """
    if not isinstance(saved_data, dict):
        saved_data = {}

    # Çekilemeyen bölümlerde kayıtlı veriyi kullan: fark çıkmaz ve kayıtta korunur.
    for section in current_data.get("failed_sections", []):
        current_data[section] = copy.deepcopy(saved_data.get(section, []))

    # Dosya kaynaklarından (Sınıf/Ders) sadece biri çekilemediyse, o kaynağın kayıtlı
    # dosyalarını koru; aksi halde hepsi "silindi" sayılıyordu.
    failed_sources = set(current_data.get("failed_file_sources", []))
    if failed_sources:
        current_data["files"] = [
            f for f in current_data.get("files", []) if f.get("source") not in failed_sources
        ] + [
            copy.deepcopy(f)
            for f in saved_data.get("files", [])
            if f.get("source") in failed_sources
        ]

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
    updated_file_entries = []  # (file_idx, file_name, change_type) for updated files
    assignment_source_entries = []  # (assign_idx, sf_idx, file_name, assign_name, is_new_assign) for source file buttons

    # --- 1. NOT KONTROLÜ ---
    for key, entry in current_grades.items():
        new_val = entry["not"]
        e_key, e_new_val = escape_html(key), escape_html(new_val)

        if key not in saved_grades:
            not_msg = f"📝 <b>YENİ NOT:</b> {e_key}\n➡️ {e_new_val}"
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
                not_msg += "\n" + escape_html("\n".join(detail_lines))
            sections_changes.append(not_msg)
            changes.append(f"YENİ NOT: {key} -> {new_val}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📝 Yeni Not: {key} -> {new_val}")
        else:
            old_entry = saved_grades[key]
            old_val = (old_entry.get("not") if isinstance(old_entry, dict) else old_entry) or "?"
            if old_val != new_val:
                e_old_val = escape_html(old_val)
                try:
                    diff = float(new_val.replace(",", ".")) - float(old_val.replace(",", "."))
                    if diff > 0:
                        trend_icon = "📈"
                        trend_label = "NOT GÜNCELLENDİ (ARTTI)"
                    else:
                        trend_icon = "📉"
                        trend_label = "NOT GÜNCELLENDİ (DÜŞTÜ)"
                except (ValueError, AttributeError):
                    trend_icon = "🔄"
                    trend_label = "NOT GÜNCELLENDİ"
                upd_msg = f"{trend_icon} <b>{trend_label}:</b> {e_key}\n{e_old_val} ➡️ {e_new_val}"
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
                    upd_msg += "\n" + escape_html("\n".join(detail_lines))
                sections_changes.append(upd_msg)
                changes.append(f"NOT GÜNCELLENDİ: {key} ({old_val} -> {new_val})")
                if include_console_log and changes_table:
                    changes_table.add_row(
                        username, course_name, f"🔄 Not Güncellendi: {key} ({old_val} -> {new_val})"
                    )

    # --- 2. ÖDEV KONTROLÜ & HATIRLATMA ---
    for assign_idx, assign in enumerate(current_assignments):
        saved_assign = next((a for a in saved_assignments if a.get("id") == assign.get("id")), None)
        e_assign_name = escape_html(assign["name"])
        e_assign_url = escape_attr(assign.get("url", ""))

        if saved_assign:
            # Ödev detay sayfası çekilemediyse (source_files anahtarı yok) detay alanlarını
            # kayıttan al; yoksa "kaynak dosya silindi"/"teslim geri çekildi" gibi sahte
            # bildirimler gidip bir sonraki kontrolde geri geliyordu.
            if "source_files" not in assign:
                for key in (
                    "description",
                    "source_files",
                    "required_files",
                    "is_submitted",
                    "detail_fetched_at",
                ):
                    if key in saved_assign:
                        assign[key] = saved_assign[key]
                # Detay önbellek meta verisi de kayıttakiyle aynı kalmalı: zaman damgası
                # düşerse taze detay her döngüde yeniden çekiliyordu; yeni liste imzası
                # kaydedilirse ise liste değişikliğinden sonraki detay hiç çekilmiyordu.
                # Kayıtlı imza ile tutarlı bırakınca sadece gerçekten gereken yeniden
                # denenir.
                assign["list_signature"] = saved_assign.get("list_signature")
            # Hatırlatma kaydını her zaman taşı (manuel kontrol include_reminders=False
            # ile çalışıyor ve bu alanı siliyordu → aynı hatırlatma tekrar gidiyordu).
            if "reminders_sent" in saved_assign:
                assign.setdefault("reminders_sent", saved_assign["reminders_sent"])

        if not saved_assign:
            new_assign_msg = (
                f"📅 <b>YENİ ÖDEV:</b> <a href='{e_assign_url}'>{e_assign_name}</a>\n"
                f"🗓 {escape_html(assign['start_date'])} ➡️ {escape_html(assign['end_date'])}"
            )
            if assign.get("description"):
                new_assign_msg += f"\n\n📝 {escape_html(assign['description'])}"
            if assign.get("required_files"):
                req_lines = "\n".join(
                    f"  • {escape_html(r['description'])}"
                    + (f" (<code>{escape_html(r['filename'])}</code>)" if r.get("filename") else "")
                    + f" [{escape_html(r['extensions'])}]"
                    for r in assign["required_files"]
                )
                new_assign_msg += f"\n\n📋 <b>İstenen Dosyalar:</b>\n{req_lines}"
            if assign.get("source_files"):
                new_assign_msg += f"\n\n📦 <b>Kaynak Dosyalar ({len(assign['source_files'])}):</b>"
                for sf_idx, sf in enumerate(assign["source_files"]):
                    assignment_source_entries.append(
                        (assign_idx, sf_idx, sf["name"], sf["size"], assign["name"], True)
                    )
            sections_changes.append(new_assign_msg)
            changes.append(f"YENİ ÖDEV: {assign['name']}")
            if include_console_log and changes_table:
                changes_table.add_row(username, course_name, f"📄 Yeni Ödev: {assign['name']}")
        else:
            if assign["end_date"] != saved_assign.get("end_date"):
                old_date = saved_assign.get("end_date", "?")
                sections_changes.append(
                    f"🕒 <b>TESLİM TARİHİ DEĞİŞTİ:</b> {e_assign_name}\n"
                    f"{escape_html(old_date)} ➡️ {escape_html(assign['end_date'])}"
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
                    f"🔄 <b>ÖDEV DURUMU GÜNCELLENDİ:</b> <a href='{e_assign_url}'>{e_assign_name}</a>\nDurum: {status_str}"
                )
                changes.append(f"ÖDEV DURUMU DEĞİŞTİ: {assign['name']} ({status_str})")

            # Açıklama değişti mi?
            old_desc = saved_assign.get("description", "")
            new_desc = assign.get("description", "")
            if new_desc and new_desc != old_desc:
                if old_desc:
                    diff_text = content_diff(old_desc, new_desc)
                    sections_changes.append(
                        f"📝 <b>ÖDEV AÇIKLAMASI DEĞİŞTİ:</b> <a href='{e_assign_url}'>{e_assign_name}</a>\n"
                        f"<pre>{escape_html(diff_text)}</pre>"
                    )
                else:
                    sections_changes.append(
                        f"📝 <b>ÖDEV AÇIKLAMASI EKLENDİ:</b> <a href='{e_assign_url}'>{e_assign_name}</a>\n"
                        f"{escape_html(new_desc)}"
                    )
                changes.append(f"ÖDEV AÇIKLAMASI DEĞİŞTİ: {assign['name']}")

            # Yeni kaynak dosya eklendi mi?
            old_src_names = {f["name"] for f in saved_assign.get("source_files", [])}
            for sf_idx, sf in enumerate(assign.get("source_files", [])):
                if sf["name"] not in old_src_names:
                    assignment_source_entries.append(
                        (assign_idx, sf_idx, sf["name"], sf["size"], assign["name"], False)
                    )
                    changes.append(f"YENİ KAYNAK DOSYA: {sf['name']}")

            # Kaynak dosya silindi mi?
            new_src_names = {f["name"] for f in assign.get("source_files", [])}
            for sf in saved_assign.get("source_files", []):
                if sf["name"] not in new_src_names:
                    sections_changes.append(
                        f"🗑️ <b>KAYNAK DOSYA SİLİNDİ:</b> <a href='{e_assign_url}'>{e_assign_name}</a>\n"
                        f"  • {escape_html(sf['name'])}"
                    )
                    changes.append(f"KAYNAK DOSYA SİLİNDİ: {sf['name']}")

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
                        f"{reminder_msg}\nBitiş: {escape_html(assign['end_date'])}\n"
                        f"<a href='{e_assign_url}'>Ödeve Git</a>"
                    )
                    changes.append(f"HATIRLATMA ({reminder_tag}): {assign['name']}")
                    assign["reminders_sent"] = [*sent_reminders, reminder_tag]
                else:
                    assign["reminders_sent"] = sent_reminders
            elif saved_assign:
                assign["reminders_sent"] = saved_assign.get("reminders_sent", [])

    # --- 3. DOSYA KONTROLÜ ---
    # Guard against transient empty file lists that would cause mass delete/add noise.
    files_suspect_count = saved_data.get("files_suspect_count", 0)
    skip_file_diff = False
    if saved_files and not current_files and files_suspect_count < 1:
        # First empty snapshot after having files: treat as suspicious and skip file diffs.
        skip_file_diff = True
        current_data["_files_suspect"] = True
        current_data["_files_suspect_count"] = files_suspect_count + 1
        logger.warning(
            "Dosya listesi bos dondu; toplu silme/ekleme bildirimini atliyorum. course=%s",
            course_name,
        )

    saved_file_map = {f.get("url"): f for f in saved_files}
    for file_idx, file in enumerate(current_files):
        if skip_file_diff:
            break
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
                change_type = "GÜNCELLENDİ" if date_changed else "ADI DEĞİŞTİ"
                updated_file_entries.append((file_idx, file["name"], change_type))
                changes.append(f"DOSYA {change_type}: {file['name']}")

    # --- 4. DUYURU KONTROLÜ ---
    saved_ann_map = {a.get("id"): a for a in saved_announcements}
    current_ann_ids = {a.get("id") for a in current_announcements}

    for ann in current_announcements:
        ann_id = ann.get("id")
        e_ann_title = escape_html(ann["title"])
        e_ann_author = escape_html(ann.get("author", ""))
        e_ann_url = escape_attr(ann.get("url", ""))

        if ann_id not in saved_ann_map:
            full_content = get_announcement_detail(user_session, ann["url"])
            ann["content"] = full_content
            ann_msg = f"📣 <b>YENİ DUYURU:</b> <a href='{e_ann_url}'>{e_ann_title}</a>"
            if e_ann_author:
                ann_msg += f"\n👤 {e_ann_author} | 📅 {escape_html(ann['date'])}"
            if full_content:
                ann_msg += f"\n\n{full_content}"
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
                diff_lines = []
                if ann["title"] != saved_ann.get("title"):
                    diff_lines.append(
                        f"📌 Başlık: {escape_html(saved_ann.get('title', ''))} ➡️ {e_ann_title}"
                    )
                if ann.get("author") != saved_ann.get("author"):
                    diff_lines.append(
                        f"👤 Yazar: {escape_html(saved_ann.get('author', ''))} ➡️ {e_ann_author}"
                    )
                if ann.get("date") != saved_ann.get("date"):
                    diff_lines.append(
                        f"📅 Tarih: {escape_html(saved_ann.get('date', '?'))} ➡️ {escape_html(ann.get('date', '?'))}"
                    )
                old_content = saved_ann.get("content", "")
                ann_upd_msg = (
                    f"🔄 <b>DUYURU GÜNCELLENDİ:</b> <a href='{e_ann_url}'>{e_ann_title}</a>"
                )
                if diff_lines:
                    ann_upd_msg += "\n" + "\n".join(diff_lines)
                if full_content and full_content != old_content and old_content:
                    diff_text = content_diff(old_content, full_content)
                    ann_upd_msg += f"\n\n<pre>{escape_html(diff_text)}</pre>"
                elif full_content:
                    ann_upd_msg += f"\n\n{full_content}"
                sections_changes.append(ann_upd_msg)
                changes.append(f"DUYURU GÜNCELLENDİ: {ann['title']}")
            else:
                ann["content"] = saved_ann.get("content", "")

    # --- 5. SİLİNMİŞ VERİLERİ KONTROL ET ---
    if current_data.get("fetch_success", True):
        current_grade_keys = set(current_grades.keys())
        for saved_key in saved_grades:
            if saved_key not in current_grade_keys:
                e_saved_key = escape_html(saved_key)
                saved_entry = saved_grades[saved_key]
                old_val = (
                    saved_entry.get("not") if isinstance(saved_entry, dict) else saved_entry
                ) or "?"
                sections_changes.append(
                    f"🗑️ <b>NOT SİLİNDİ:</b> {e_saved_key} (eski: {escape_html(old_val)})"
                )
                changes.append(f"NOT SİLİNDİ: {saved_key}")

        current_assign_ids = {a.get("id") for a in current_assignments}
        for sa in saved_assignments:
            if sa.get("id") not in current_assign_ids:
                e_name = escape_html(sa.get("name", "Bilinmeyen Ödev"))
                sections_changes.append(f"🗑️ <b>ÖDEV SİLİNDİ:</b> {e_name}")
                changes.append(f"ÖDEV SİLİNDİ: {sa.get('name')}")

        if not skip_file_diff:
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

    return (
        sections_changes,
        changes,
        new_file_entries,
        updated_file_entries,
        assignment_source_entries,
    )
