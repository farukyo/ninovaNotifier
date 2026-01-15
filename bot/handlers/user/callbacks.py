import contextlib
import math

import requests
from telebot import types

from bot.instance import bot_instance as bot
from bot.keyboards import build_cancel_keyboard, build_main_keyboard, build_manual_menu
from bot.utils import show_file_browser
from common.cache import get_cached_file_id, set_cached_file_id
from common.config import HEADERS, USER_SESSIONS, load_all_users, save_all_users
from common.utils import (
    decrypt_password,
    delete_course_data,
    escape_html,
    get_file_icon,
    load_saved_grades,
    sanitize_html_for_telegram,
    save_grades,
    send_telegram_document,
    update_user_data,
)
from services.ninova import download_file


def _is_cancel_text(text: str) -> bool:
    """Check if the message text indicates a cancel action."""
    if not text:
        return False
    t = text.strip().lower()
    return "iptal" in t or "cancel" in t or "⛔" in text


@bot.callback_query_handler(func=lambda call: call.data.startswith("crs_"))
def handle_course_selection(call):
    """
    Kullanıcı bir ders seçtiğinde çalışır.
    Ders detay menüsünü (Not, Ödev, Dosya, Duyuru) gösterir.
    """
    chat_id = str(call.message.chat.id)
    course_idx = int(call.data.split("_")[1])

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if course_idx >= len(urls):
        bot.answer_callback_query(call.id, "Ders bulunamadı.")
        return

    url = urls[course_idx]
    data = user_grades[url]
    course_name = data.get("course_name", "Bilinmeyen Ders")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Notlar", callback_data=f"det_{course_idx}_not"),
        types.InlineKeyboardButton("📅 Ödevler", callback_data=f"det_{course_idx}_odev"),
        types.InlineKeyboardButton("📁 Dosyalar", callback_data=f"det_{course_idx}_dosya"),
        types.InlineKeyboardButton("📣 Duyurular", callback_data=f"det_{course_idx}_duyuru"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data=f"kontrol_{course_idx}"))
    markup.add(types.InlineKeyboardButton("↩️ Ana Menü", callback_data="main_menu"))

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"🎓 <b>{course_name}</b>\nLütfen görmek istediğiniz kategoriyi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ann_"))
def handle_announcement_detail(call):
    """
    Seçilen duyurunun detayını gösterir.
    """
    parts = call.data.split("_")
    course_idx = int(parts[1])
    ann_idx = int(parts[2])

    chat_id = str(call.message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if course_idx >= len(urls):
        bot.answer_callback_query(call.id, "Ders bulunamadı.")
        return

    url = urls[course_idx]
    data = user_grades[url]
    announcements = data.get("announcements", [])

    if ann_idx >= len(announcements):
        bot.answer_callback_query(call.id, "Duyuru bulunamadı.")
        return

    ann = announcements[ann_idx]

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"det_{course_idx}_duyuru"))

    # Sanitize content before sending to Telegram
    raw_content = ann.get("content", "İçerik yüklenemedi.")
    content = sanitize_html_for_telegram(raw_content)[:3000]

    text = (
        f"📣 <b>{escape_html(ann['title'])}</b>\n"
        f"👤 {escape_html(ann.get('author', ''))} | 📅 {ann.get('date', '')}\n"
        f"🔗 <a href='{ann['url']}'>Ninova'da Oku</a>\n\n"
        f"{content}"
    )

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("det_"))
def handle_course_detail(call):
    """
    Ders detay menüsünden bir seçenek (Not, Ödev vb.) seçildiğinde,
    ilgili içeriği listeler.
    """
    chat_id = str(call.message.chat.id)
    parts = call.data.split("_")
    course_idx, detail_type = int(parts[1]), parts[2]

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if course_idx >= len(urls):
        bot.answer_callback_query(call.id, "Ders bulunamadı.")
        return

    url = urls[course_idx]
    data = user_grades[url]
    course_name = data.get("course_name", "Bilinmeyen Ders")

    markup = types.InlineKeyboardMarkup()
    response = f"🎓 <b>{course_name}</b>\n\n"

    if detail_type == "not":
        response += "📊 <b>Notlar:</b>\n"
        grades = data.get("grades", {})
        if not grades:
            response += "<i>Not bulunamadı.</i>"
        else:
            total_weight = 0.0
            weighted_avg_sum = 0.0
            weighted_var_sum = 0.0
            user_weighted_avg_sum = 0.0

            for key, val in grades.items():
                # Extract weight safely
                w_raw = val.get("agirlik", "").replace("%", "").replace(",", ".").strip()
                try:
                    w_val = float(w_raw)
                except ValueError:
                    w_val = 0.0

                details = val.get("detaylar", {})
                class_avg = 0.0
                std_dev = 0.0
                has_stats = False

                if "class_avg" in details:
                    with contextlib.suppress(ValueError):
                        class_avg = float(details["class_avg"].replace(",", "."))
                        has_stats = True

                if "std_dev" in details:
                    with contextlib.suppress(ValueError):
                        std_dev = float(details["std_dev"].replace(",", "."))

                score = val.get("not", "?")
                weight_str = f" (%{w_val:g})" if w_val > 0 else ""

                # Format the grade line
                response += f"▫️ {key}: <b>{score}</b>{weight_str}\n"

                # Sub-line details
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
                    response += f"   <i>└ {', '.join(detail_lines)}</i>\n"

                # Cumulative Calculations
                if w_val > 0:
                    w_norm = w_val / 100.0
                    total_weight += w_val

                    try:
                        user_grade_val = float(str(score).replace(",", "."))
                        user_weighted_avg_sum += w_norm * user_grade_val
                    except (ValueError, TypeError):
                        pass

                    if has_stats:
                        weighted_avg_sum += w_norm * class_avg
                        weighted_var_sum += (w_norm * w_norm) * (std_dev * std_dev)

            # Cumulative Summary Footer
            if total_weight > 0:
                c_avg = f"{weighted_avg_sum:.2f}"
                c_std = f"{math.sqrt(weighted_var_sum):.2f}"
                u_avg = f"{user_weighted_avg_sum:.2f}"

                response += "\n----------------------------\n"
                response += f"📊 <b>Ortalamanız: {u_avg}</b> | Sınıf geneli: Ort: {c_avg}, Std: {c_std} (%{total_weight:g} veriye göre)\n"

            # Add Visualization Button
            # We check if there's any grade with stats to justify showing the button
            has_any_stats = any(
                "class_avg" in v.get("detaylar", {}) and "std_dev" in v.get("detaylar", {})
                for v in grades.values()
            )
            if has_any_stats:
                markup.add(
                    types.InlineKeyboardButton(
                        "📈 Grafikleştir", callback_data=f"graph_{course_idx}"
                    )
                )

    elif detail_type == "odev":
        response += "📅 <b>Ödevler:</b>\n"
        assignments = data.get("assignments", [])
        if not assignments:
            response += "<i>Ödev bulunamadı.</i>"
        else:
            for assign in assignments:
                status = "✅" if assign.get("is_submitted") else "❌"
                response += f"{status} <a href='{assign['url']}'>{assign['name']}</a>\n└ ⏳ Bitiş: <code>{assign['end_date']}</code>\n"

    elif detail_type == "dosya":
        bot.answer_callback_query(call.id)
        show_file_browser(chat_id, call.message.message_id, course_idx, "")
        return

    elif detail_type == "duyuru":
        response += "📣 <b>Duyurular:</b>\n<i>(Okumak için butona tıklayın)</i>\n\n"
        announcements = data.get("announcements", [])
        if not announcements:
            response += "<i>Duyuru bulunamadı.</i>"
        else:
            for i, ann in enumerate(announcements[:10]):
                title = ann["title"]
                if len(title) > 25:
                    title = title[:25] + "..."
                markup.add(
                    types.InlineKeyboardButton(f"🔹 {title}", callback_data=f"ann_{course_idx}_{i}")
                )

    markup.add(types.InlineKeyboardButton("↩️ Geri Dön", callback_data=f"crs_{course_idx}"))
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=response,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("graph_"))
def handle_course_graph(call):
    """
    Generates and sends a bell curve graph for the selected course.
    """
    chat_id = str(call.message.chat.id)
    course_idx = int(call.data.split("_")[1])

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if course_idx >= len(urls):
        bot.answer_callback_query(call.id, "Ders bulunamadı.")
        return

    url = urls[course_idx]
    data = user_grades[url]
    course_name = data.get("course_name", "Bilinmeyen Ders")
    grades = data.get("grades", {})

    bot.answer_callback_query(call.id, "Grafik oluşturuluyor...", show_alert=False)
    bot.send_chat_action(chat_id, "upload_photo")

    try:
        from services.visualization import generate_bell_curve

        image_buffer = generate_bell_curve(grades)

        if image_buffer:
            bot.send_photo(
                chat_id,
                image_buffer,
                caption=f"📈 <b>{course_name}</b> - Başarı Dağılımı",
                parse_mode="HTML",
            )
            image_buffer.close()
        else:
            bot.send_message(chat_id, "⚠️ Bu ders için yeterli istatistik verisi bulunamadı.")

    except ImportError:
        bot.send_message(chat_id, "⚠️ Görselleştirme modülü yüklenemedi.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Grafik oluşturulurken hata oluştu: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu(call):
    """
    Ana menüye/ders listesine geri döner.

    Kullanıcı detay sayfalarından ana ders listesine dönmek için kullanılır.

    :param call: CallbackQuery nesnesi
    """
    chat_id = str(call.message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    markup = types.InlineKeyboardMarkup()
    for i, (_url, data) in enumerate(user_grades.items()):
        markup.add(
            types.InlineKeyboardButton(
                f"📚 {data.get('course_name', 'Bilinmeyen Ders')}",
                callback_data=f"crs_{i}",
            )
        )

    # Add general control button
    markup.add(types.InlineKeyboardButton("🔄 Tümünü Kontrol Et", callback_data="global_kontrol"))
    # Add Manual Course Menu button
    markup.add(
        types.InlineKeyboardButton("📝 Manuel Ders Yönetimi", callback_data="manual_menu_open")
    )

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_"))
def handle_file_download(call):
    """
    Dosya indirme işlemini başlatır ve dosyayı Telegram üzerinden gönderir (Hızlı).
    """
    chat_id = str(call.message.chat.id)
    parts = call.data.split("_")
    url_idx, file_idx = int(parts[1]), int(parts[2])

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    urls = list(user_grades.keys())

    if url_idx >= len(urls):
        bot.answer_callback_query(call.id, "Kurs bulunamadı.")
        return

    course_url = urls[url_idx]
    files = user_grades[course_url].get("files", [])
    if file_idx >= len(files):
        bot.answer_callback_query(call.id, "Dosya bulunamadı.")
        return

    file_data = files[file_idx]
    file_url = file_data["url"]
    file_name = (
        file_data["name"] if "/" not in file_data["name"] else file_data["name"].split("/")[-1]
    )

    # 1. Check Cache
    cached_id = get_cached_file_id(file_url)
    if cached_id:
        bot.answer_callback_query(call.id, "🚀 Hızlı gönderiliyor...")
        send_telegram_document(
            chat_id,
            cached_id,
            caption=f"{get_file_icon(file_name)} {file_name}",
            is_file_id=True,
            filename=file_name,
        )
        return

    # 2. Download and Send
    bot.answer_callback_query(call.id, "Dosya indiriliyor...")
    bot.send_chat_action(chat_id, "upload_document")

    users = load_all_users()
    user_info = users.get(chat_id, {})
    username = user_info.get("username")
    password = decrypt_password(user_info.get("password", ""))

    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = requests.Session()
        USER_SESSIONS[chat_id].headers.update(HEADERS)

    session = USER_SESSIONS[chat_id]

    # Download to buffer (RAM)
    result = download_file(
        session,
        file_url,
        file_name,
        chat_id=chat_id,
        username=username,
        password=password,
        to_buffer=True,
    )

    if result:
        file_buffer, final_filename = result
        # Send
        sent_id = send_telegram_document(
            chat_id,
            file_buffer,
            caption=f"{get_file_icon(final_filename)} {final_filename}",
            filename=final_filename,
        )

        # Cache the file ID for future
        if sent_id:
            set_cached_file_id(file_url, sent_id)

        file_buffer.close()
    else:
        bot.send_message(chat_id, "❌ Dosya indirilemedi.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dir_"))
def handle_directory_navigation(call):
    """
    Dosya tarayıcısında klasörler arası gezinmeyi sağlar.

    Kullanıcı klasör seçtiğinde o klasörün içeriğini gösterir.

    :param call: CallbackQuery nesnesi (dir_<course_idx>_<path> formatında)
    """
    # Kalan kodun devamı olması gerekirdi ancak dosya kesik görünüyor.
    # Muhtemelen show_file_browser çağırılacak.

    parts = call.data.split("_", 2)
    course_idx = int(parts[1])
    path_str = parts[2] if len(parts) > 2 else ""

    show_file_browser(str(call.message.chat.id), call.message.message_id, course_idx, path_str)


def handle_folder_navigation(call):
    """Handle folder navigation in the inline file browser."""
    parts = call.data.split("_", 2)
    course_idx = int(parts[1])
    path_str = parts[2] if len(parts) > 2 else ""
    bot.answer_callback_query(call.id)
    show_file_browser(str(call.message.chat.id), call.message.message_id, course_idx, path_str)


@bot.callback_query_handler(func=lambda call: call.data == "leave_confirm")
def handle_leave_confirm(call):
    """Confirm leaving: delete user data, cached grades, and close session."""
    chat_id = str(call.message.chat.id)
    users = load_all_users()
    if chat_id in users:
        del users[chat_id]
    save_all_users(users)
    all_grades = load_saved_grades()
    if chat_id in all_grades:
        del all_grades[chat_id]
    save_grades(all_grades)
    if chat_id in USER_SESSIONS:
        try:
            USER_SESSIONS[chat_id].close()
            del USER_SESSIONS[chat_id]
        except Exception:
            pass
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="✅ Tüm verileriniz silindi. Tekrar görüşmek üzere!",
    )


@bot.callback_query_handler(func=lambda call: call.data == "leave_cancel")
def handle_leave_cancel(call):
    """Cancel leaving flow and keep user data intact."""
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Vazgeçildi, sistemde kalmaya devam ediyorsunuz.",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def handle_course_delete_any(call):
    """Handle course deletion flows (request/confirm/cancel) via callbacks."""
    # This might need refinement based on startswith logic overlaps
    if call.data.startswith("del_req_"):
        idx = int(call.data.split("_")[2])
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Evet, Sil", callback_data=f"del_yes_{idx}"),
            types.InlineKeyboardButton("Hayır", callback_data="del_no"),
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Bu dersi silmek istediğinizden emin misiniz?",
            reply_markup=markup,
        )
    elif call.data.startswith("del_yes_"):
        chat_id = str(call.message.chat.id)
        idx = int(call.data.split("_")[2])
        users = load_all_users()
        user_data = users.get(chat_id, {})
        urls = user_data.get("urls", [])
        if idx < len(urls):
            # Önce veriyi sil (Deep Clean)
            course_url = urls[idx]
            delete_course_data(chat_id, course_url)

            # Sonra listeyi kullanıcıdan sil
            del users[chat_id]["urls"][idx]
            save_all_users(users)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="✅ Ders ve ilgili tüm veriler başarıyla silindi.",
            )
    elif call.data == "del_no":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Silme işlemi iptal edildi.",
        )


@bot.callback_query_handler(func=lambda call: call.data == "manual_menu_open")
def handle_manual_menu_open(call):
    """
    Manuel ders yönetimi menüsünü açar (Inline).
    """
    markup = build_manual_menu()
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📝 <b>Manuel Ders Yönetimi</b>\n\nİstediğiniz işlemi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "manual_add")
def handle_manual_add(call):
    """
    Manuel ders ekleme işlemi başlatır.
    """
    chat_id = str(call.message.chat.id)
    # Edit the inline message for context, then send a new message with a cancel keyboard
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="➕ <b>Ders Ekleme</b>\n\nLütfen Ninova ders linkini gönderin:\n<code>https://ninova.itu.edu.tr/Sinif/123.456</code>",
        parse_mode="HTML",
    )
    prompt = bot.send_message(
        chat_id,
        "Lütfen ders linkini yazın veya 'İptal' tuşuna basın.",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_manual_add)


@bot.callback_query_handler(func=lambda call: call.data == "manual_delete")
def handle_manual_delete(call):
    """
    Manuel ders silme menüsünü gösterir.
    """
    chat_id = str(call.message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])
    from common.utils import load_saved_grades

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not urls:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="❌ Takip ettiğiniz ders bulunamadı.",
        )
        return

    markup = types.InlineKeyboardMarkup()
    for i, url in enumerate(urls):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i + 1}")
        display_text = course_name if len(course_name) <= 40 else course_name[:37] + "..."
        markup.add(types.InlineKeyboardButton(f"🗑️ {display_text}", callback_data=f"del_req_{i}"))

    markup.add(types.InlineKeyboardButton("↩️ Geri", callback_data="manual_back"))

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="🗑️ <b>Ders Silme</b>\n\nSilmek istediğiniz dersi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "manual_list")
def handle_manual_list(call):
    """
    Takip edilen dersleri listeler.
    """
    chat_id = str(call.message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])
    from common.utils import load_saved_grades

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not urls:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="❌ Takip ettiğiniz ders bulunamadı.",
        )
        return

    response = "📋 <b>Takip Ettiğiniz Dersler:</b>\n\n"
    for i, url in enumerate(urls, 1):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i}")
        response += f"{i}. <b>{course_name}</b>\n<code>{url}</code>\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("↩️ Geri", callback_data="manual_back"))

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=response,
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "manual_back")
def handle_manual_back(call):
    """
    Manuel ders menüsüne geri döner.
    """
    markup = build_manual_menu()
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📝 <b>Manuel Ders Yönetimi</b>\n\nİstediğiniz işlemi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


def process_manual_add(message):
    """
    Manuel ders ekleme işlemini tamamlar.
    """
    # Allow cancellation via button or typed text
    if _is_cancel_text(message.text):
        bot.send_message(
            message.chat.id,
            "❌ Ders ekleme iptal edildi.",
            reply_markup=build_main_keyboard(),
        )
        return

    if not message.text:
        bot.send_message(
            message.chat.id,
            "❌ Geçerli bir değer girmediniz.",
            reply_markup=build_main_keyboard(),
        )
        return

    args = message.text.split()
    if len(args) < 1 or "ninova.itu.edu.tr" not in args[0]:
        bot.send_message(
            message.chat.id,
            "❌ Lütfen geçerli bir Ninova ders linki girin.\nÖrn: <code>https://ninova.itu.edu.tr/Sinif/123.456</code>",
            parse_mode="HTML",
        )
        return

    url = args[0].split("?")[0].strip()
    # Alt sayfa varsa temizle, base URL olarak sakla
    for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break

    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])

    if url in urls:
        bot.send_message(
            message.chat.id,
            "⚠️ Bu ders zaten takip ediliyor.",
        )
        return

    urls.append(url)
    update_user_data(chat_id, "urls", urls)
    bot.send_message(
        message.chat.id,
        f"✅ Ders başarıyla eklendi!\n<code>{url}</code>",
        parse_mode="HTML",
    )


@bot.callback_query_handler(
    func=lambda call: call.data == "global_kontrol" or call.data.startswith("kontrol_")
)
def handle_kontrol(call):
    """
    Kullanıcının derslerini manuel olarak kontrol eder.
    """
    chat_id = str(call.message.chat.id)
    course_idx = None
    if call.data.startswith("kontrol_"):
        with contextlib.suppress(IndexError, ValueError):
            course_idx = int(call.data.split("_")[1])

    bot.answer_callback_query(call.id, "Kontrol başlatıldı, lütfen bekleyin...")

    # Edit message to show status
    try:
        text = "🔄 <b>Manuel Kontrol Yapılıyor...</b>\nYeni bir not, ödev veya duyuru olup olmadığı kontrol ediliyor. Bu işlem birkaç saniye sürebilir."
        if course_idx is not None:
            text = "🔄 <b>Bu Ders Kontrol Ediliyor...</b>\nDers verileri Ninova'dan tazeleniyor."

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception:
        pass

    def run_check():
        try:
            from main import check_user_updates

            result = check_user_updates(chat_id, course_idx=course_idx)

            if result.get("success"):
                bot.send_message(
                    chat_id,
                    "✅ Kontrol tamamlandı. Not, ödev, dosya ve duyuru bilgileriniz güncellendi.",
                )
            else:
                bot.send_message(
                    chat_id,
                    f"❌ Kontrol sırasında bir hata oluştu: {result.get('message', 'Bilinmeyen hata')}",
                )

            # Re-show the appropriate menu
            if course_idx is not None:
                # Go back to course detail
                all_grades = load_saved_grades()
                user_grades = all_grades.get(chat_id, {})
                urls = list(user_grades.keys())

                if course_idx < len(urls):
                    url = urls[course_idx]
                    data = user_grades[url]
                    course_name = data.get("course_name", "Bilinmeyen Ders")

                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton(
                            "📊 Notlar", callback_data=f"det_{course_idx}_not"
                        ),
                        types.InlineKeyboardButton(
                            "📅 Ödevler", callback_data=f"det_{course_idx}_odev"
                        ),
                        types.InlineKeyboardButton(
                            "📁 Dosyalar", callback_data=f"det_{course_idx}_dosya"
                        ),
                        types.InlineKeyboardButton(
                            "📣 Duyurular", callback_data=f"det_{course_idx}_duyuru"
                        ),
                    )
                    markup.add(
                        types.InlineKeyboardButton(
                            "🔄 Tekrar Kontrol Et",
                            callback_data=f"kontrol_{course_idx}",
                        )
                    )
                    markup.add(types.InlineKeyboardButton("↩️ Ana Menü", callback_data="main_menu"))

                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=call.message.message_id,
                            text=f"🎓 <b>{course_name}</b> (Güncellendi)\nLütfen bir kategori seçin:",
                            reply_markup=markup,
                            parse_mode="HTML",
                        )
                    except Exception:
                        # Fallback to sending a new message if editing fails
                        bot.send_message(
                            chat_id,
                            f"🎓 <b>{course_name}</b> (Güncellendi)\nLütfen bir kategori seçin:",
                            reply_markup=markup,
                            parse_mode="HTML",
                        )
                return

            # Global refresh - Show main menu
            all_grades = load_saved_grades()
            user_grades = all_grades.get(chat_id, {})
            markup = types.InlineKeyboardMarkup()
            for i, (_url, data) in enumerate(user_grades.items()):
                markup.add(
                    types.InlineKeyboardButton(
                        f"📚 {data.get('course_name', 'Bilinmeyen Ders')}",
                        callback_data=f"crs_{i}",
                    )
                )
            markup.add(
                types.InlineKeyboardButton("🔄 Tümünü Kontrol Et", callback_data="global_kontrol")
            )

            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text="📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
                    reply_markup=markup,
                    parse_mode="HTML",
                )
            except Exception:
                # Fallback to sending a new message if editing fails
                bot.send_message(
                    chat_id,
                    "📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
                    reply_markup=markup,
                    parse_mode="HTML",
                )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Kritik hata: {str(e)}")

    import threading

    threading.Thread(target=run_check, daemon=True).start()


@bot.callback_query_handler(func=lambda call: call.data == "show_all_assignments")
def handle_show_all_assignments(call):
    """
    Kullanıcı 'Tümünü Göster' dediğinde, ödev listesini filtrelemeden tekrar gönderir.
    """
    # Mevcut mesajı sil (temiz görüntü için)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    from bot.handlers.user.grade_commands import list_assignments

    # show_all=True ile çağır
    list_assignments(call.message, show_all=True)


@bot.callback_query_handler(func=lambda call: call.data == "add_expired_yes")
def handle_add_expired_yes(call):
    """
    Kullanıcı eski dönem derslerinin eklenmesini onayladığında çalışır.
    """
    # Mesajı güncelle
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⏳ Eski dönem dersleri ekleniyor ve senkronize ediliyor...",
    )

    chat_id = str(call.message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})

    # Temp listeyi al
    expired_urls = user_data.get("temp_expired_courses", [])
    if not expired_urls:
        bot.send_message(chat_id, "⚠️ Eklenecek eski ders bulunamadı (liste boş).")
        return

    # Ekle
    current_urls = user_data.get("urls", [])
    updated_urls = list(set(current_urls + expired_urls))
    update_user_data(chat_id, "urls", updated_urls)

    # Temp'i sil
    if "temp_expired_courses" in users[chat_id]:
        del users[chat_id]["temp_expired_courses"]
        save_all_users(users)

    # Senkronizasyon başlat
    def run_sync():
        from main import check_user_updates

        result = check_user_updates(chat_id, silent=True)

        if result.get("success"):
            bot.send_message(
                chat_id,
                f"✅ <b>İşlem Tamamlandı!</b>\n"
                f"{len(expired_urls)} adet eski dönem dersi listenize eklendi.",
                parse_mode="HTML",
            )
        else:
            bot.send_message(
                chat_id,
                f"⚠️ Dersler eklendi ancak senkronizasyon sırasında hata oluştu: {result.get('message')}",
            )

    import threading

    threading.Thread(target=run_sync, daemon=True).start()


@bot.callback_query_handler(func=lambda call: call.data == "add_expired_no")
def handle_add_expired_no(call):
    """
    Kullanıcı eski dönem derslerini reddettiğinde çalışır.
    """
    chat_id = str(call.message.chat.id)
    # Temp'i sil
    users = load_all_users()
    if chat_id in users and "temp_expired_courses" in users[chat_id]:
        del users[chat_id]["temp_expired_courses"]
        save_all_users(users)

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🙅‍♂️ Eski dönem dersleri eklenmedi. Sadece aktif dersler listenizde.",
    )


@bot.callback_query_handler(func=lambda call: call.data == "show_past_calendar")
def handle_show_past_calendar(call):
    """
    Kullanıcı akademik takvimde geçmiş etkinlikleri görmek istediğinde çalışır.
    """
    from services.calendar import ITUCalendarService

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔄 Geçmiş etkinlikler yükleniyor...",
    )

    try:
        data = ITUCalendarService.get_filtered_calendar(show_past=True, show_future=False)

        from telebot import types

        from common.utils import split_long_message

        chunks = split_long_message(data)

        # Delete the loading message
        bot.delete_message(call.message.chat.id, call.message.message_id)

        # Check if there are still hidden future events
        markup = None
        if "uzak gelecek etkinlik gizlendi" in data:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📅 Gelecektekileri Göster", callback_data="show_future_calendar"
                )
            )

        # Send calendar with past events
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                bot.send_message(
                    call.message.chat.id, chunk, parse_mode="HTML", reply_markup=markup
                )
            else:
                bot.send_message(call.message.chat.id, chunk, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ Hata: {str(e)}",
        )


@bot.callback_query_handler(func=lambda call: call.data == "show_future_calendar")
def handle_show_future_calendar(call):
    """
    Kullanıcı 10 günden uzak etkinlikleri görmek istediğinde çalışır.
    """
    from services.calendar import ITUCalendarService

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔄 Uzak gelecek etkinlikleri yükleniyor...",
    )

    try:
        data = ITUCalendarService.get_filtered_calendar(show_past=False, show_future=True)

        from telebot import types

        from common.utils import split_long_message

        chunks = split_long_message(data)

        # Delete the loading message
        bot.delete_message(call.message.chat.id, call.message.message_id)

        # Check if there are still hidden past events
        markup = None
        if "geçmiş etkinlik gizlendi" in data:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("📜 Geçmişi Göster", callback_data="show_past_calendar")
            )

        # Send calendar with future events
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                bot.send_message(
                    call.message.chat.id, chunk, parse_mode="HTML", reply_markup=markup
                )
            else:
                bot.send_message(call.message.chat.id, chunk, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ Hata: {str(e)}",
        )


# Admin callback handlers - admin/callbacks.py'de tanımlı
# @bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
# def handle_admin_callbacks(call):
