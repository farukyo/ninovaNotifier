"""
Not ve ödev komutları.
"""

import contextlib
import math
import threading
from datetime import datetime

from telebot import types

from bot.instance import bot_instance as bot
from common.utils import load_saved_grades, split_long_message

from .course_commands import interactive_menu


@bot.message_handler(func=lambda message: message.text == "📊 Notlar")
def list_grades(message):
    """
    Kullanıcının kayıtlı notlarını listeler.
    Notlar, ağırlıklar, sınıf ortalaması ve performans tahmini içerir.
    """
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz kayıtlı not bulunamadı.")
        return

    response = "📊 <b>Mevcut Notlarınız:</b>\n\n"
    for data in user_grades.values():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        grades = data.get("grades", {})
        response += f"📚 <b>{course_name}</b>\n"
        if not grades:
            response += "<i>Henüz not girilmemiş.</i>\n"
        else:
            response += f"<code>{'Sınav':<15} | {'%':>3} | {'Not':>5}</code>\n"
            response += f"<code>{'-' * 28}</code>\n"

        total_weight = 0.0
        weighted_avg_sum = 0.0
        weighted_var_sum = 0.0
        user_weighted_avg_sum = 0.0

        for exam, info in grades.items():
            w_raw = info.get("agirlik", "").replace("%", "").replace(",", ".").strip()
            try:
                w_val = float(w_raw)
            except ValueError:
                w_val = 0.0

            details = info.get("detaylar", {})
            class_avg = 0.0
            std_dev = 0.0
            has_stats = False

            if "class_avg" in details:
                try:
                    class_avg = float(details["class_avg"].replace(",", "."))
                    has_stats = True
                except ValueError:
                    pass

            if "std_dev" in details:
                with contextlib.suppress(ValueError):
                    std_dev = float(details["std_dev"].replace(",", "."))

            w_disp = f"{w_val:g}" if w_val > 0 else ""
            response += f"<code>{exam[:15]:<15} | {w_disp:>3} | {info['not']:>5}</code>"

            detail_lines = []
            if "class_avg" in details:
                detail_lines.append(f"Ort: {details['class_avg']}")
            if "std_dev" in details:
                detail_lines.append(f"Std: {details['std_dev']}")
            if "student_count" in details:
                detail_lines.append(f"Kişi: {details['student_count']}")
            if "rank" in details:
                detail_lines.append(f"Sıra: {details['rank']}")

            if detail_lines:
                response += f"\n   <i>└ {', '.join(detail_lines)}</i>"
            response += "\n"

            if w_val > 0:
                w_norm = w_val / 100.0
                total_weight += w_val

                try:
                    user_grade_val = float(str(info["not"]).replace(",", "."))
                    user_weighted_avg_sum += w_norm * user_grade_val
                except (ValueError, TypeError):
                    pass

                if has_stats:
                    weighted_avg_sum += w_norm * class_avg
                    weighted_var_sum += (w_norm * w_norm) * (std_dev * std_dev)

        if total_weight > 0:
            c_avg = f"{weighted_avg_sum:.2f}"
            c_std = f"{math.sqrt(weighted_var_sum):.2f}"
            u_avg = f"{user_weighted_avg_sum:.2f}"

            response += "----------------------------\n"
            response += f"📊 <b>Ortalamanız: {u_avg}</b> | Sınıf geneli: Ort: {c_avg}, Std: {c_std} (%{total_weight:g} veriye göre)\n"

        response += "\n"

    chunks = split_long_message(response)
    for chunk in chunks:
        bot.send_message(message.chat.id, chunk, parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text == "📅 Ödevler")
def list_assignments(message, show_all=False):
    """
    Kullanıcının ödevlerini ve teslim durumlarını listeler.
    Varsayılan olarak sadece 'aktif' ödevleri gösterir.
    """
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz kayıtlı veri bulunamadı.")
        return

    from common.utils import get_assignment_status, parse_turkish_date

    total_assignments_count = 0
    hidden_assignments_count = 0
    response_lines = []

    # Tüm dersleri gez
    for data in user_grades.values():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        assignments = data.get("assignments", [])

        if not assignments:
            continue

        # Ödevleri parse et ve durumlarını hesapla
        parsed_assignments = []
        for assign in assignments:
            icon, is_active = get_assignment_status(assign)
            # Tarihe göre sıralama için datetime objesi al
            dt = parse_turkish_date(assign.get("end_date", ""))
            parsed_assignments.append(
                {
                    "data": assign,
                    "icon": icon,
                    "is_active": is_active,
                    "dt": dt or datetime.max,  # Parse edilemezse en sona at
                }
            )

        # Tarihe göre sırala (Yakın tarih en üstte)
        parsed_assignments.sort(key=lambda x: x["dt"])

        # Filtreleme
        visible_assignments = []
        for item in parsed_assignments:
            total_assignments_count += 1
            if show_all or item["is_active"]:
                visible_assignments.append(item)
            else:
                hidden_assignments_count += 1

        if visible_assignments:
            response_lines.append(f"📚 <b>{course_name}</b>")
            for item in visible_assignments:
                assign = item["data"]
                icon = item["icon"]
                response_lines.append(
                    f"{icon} <a href='{assign['url']}'>{assign['name']}</a>\n└ ⏳ Son Teslim: <code>{assign['end_date']}</code>"
                )
            response_lines.append("")  # Dersler arası boşluk

    if total_assignments_count == 0:
        bot.reply_to(
            message, "🎉 <b>Harika! Hiç ödeviniz yok.</b> Keyfinize bakın! ☕", parse_mode="HTML"
        )
        return

    if not response_lines and hidden_assignments_count > 0:
        response = "📅 <b>Aktif ödeviniz yok!</b>\n"
        response += f"\n<i>({hidden_assignments_count} geçmiş ödev gizlendi.)</i>"
    elif response_lines:
        response = "📅 <b>Ödev Durumları:</b>\n\n" + "\n".join(response_lines)
    else:
        # Should be covered by total_assignments_count == 0, but safe fallback
        response = "📅 <b>Ödev Durumları:</b>\n\n<i>Kayıtlı ödev bulunamadı.</i>"

    markup = None
    if hidden_assignments_count > 0 and not show_all:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                f"📜 Tümünü Göster ({hidden_assignments_count} Gizli)",
                callback_data="show_all_assignments",
            )
        )

    chunks = split_long_message(response)
    for i, chunk in enumerate(chunks):
        # Sadece son parça ile buton gönder
        if i == len(chunks) - 1:
            bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, chunk, parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text == "🔄 Kontrol")
def kontrol_command_handler(message):
    """
    Manuel kontrol komudu.
    /kontrol ders -> Ders listesini ve kontrol butonlarını gösterir.
    /kontrol force -> (Admin) Tüm kullanıcıları kontrol eder.
    """
    chat_id = str(message.chat.id)
    text = message.text.split()

    # 1. /kontrol force (Admin only)
    if len(text) > 1 and text[1].lower() == "force":
        from bot.handlers.admin.helpers import is_admin

        if is_admin(message):
            from bot.instance import get_check_callback

            cb = get_check_callback()
            if cb:
                bot.reply_to(
                    message,
                    "🚀 <b>Sistem Geneli Kontrol:</b> Tüm kullanıcılar için tarama başlatıldı...",
                    parse_mode="HTML",
                )
                threading.Thread(target=cb, daemon=True).start()
            else:
                bot.reply_to(message, "❌ Kontrol fonksiyonu bulunamadı.")
        else:
            bot.reply_to(message, "⛔ Bu işlem için yetkiniz bulunmuyor.")
        return

    # 2. /kontrol ders -> Ders menüsünü aç
    if len(text) > 1 and text[1].lower() == "ders":
        interactive_menu(message)
        return

    # 3. /kontrol (Düz) -> Kullanıcının tüm derslerini kontrol et
    bot.reply_to(
        message,
        "🔄 <b>Kontrol Başlatıldı:</b> Tüm dersleriniz taranıyor, lütfen bekleyin...",
        parse_mode="HTML",
    )

    def run_user_check():
        from main import check_user_updates

        result = check_user_updates(chat_id)
        if result.get("success"):
            bot.send_message(
                chat_id,
                "✅ <b>Kontrol Tamamlandı.</b>\nNot, ödev, dosya ve duyuru bilgileriniz güncellendi.",
                parse_mode="HTML",
            )
        else:
            bot.send_message(chat_id, f"❌ <b>Hata:</b> {result.get('message')}", parse_mode="HTML")

    threading.Thread(target=run_user_check, daemon=True).start()


def manual_check(message):
    """
    Kullanıcı talebiyle manuel not kontrolü başlatır.
    """
    chat_id = str(message.chat.id)
    bot.reply_to(message, "🔄 Kontrol başlatılıyor, lütfen bekleyin...")

    from main import check_user_updates

    result = check_user_updates(chat_id)

    if result["success"]:
        bot.send_message(chat_id, f"✅ {result['message']}")
    else:
        bot.send_message(chat_id, f"❌ Kontrol başarısız: {result['message']}")
