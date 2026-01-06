import requests
from telebot import types
from bot.core import bot_instance as bot
from bot.utils import show_file_browser
from core.config import load_all_users, save_all_users, HEADERS, USER_SESSIONS
from core.utils import (
    load_saved_grades,
    save_grades,
    send_telegram_document,
    get_file_icon,
    escape_html,
    decrypt_password,
)
from ninova import download_file


@bot.callback_query_handler(func=lambda call: call.data.startswith("crs_"))
def handle_course_selection(call):
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
    markup.add(
        types.InlineKeyboardButton("🔙 Geri", callback_data=f"det_{course_idx}_duyuru")
    )

    content = ann.get("content", "İçerik yüklenemedi.")[:3000]

    text = (
        f"📣 <b>{escape_html(ann['title'])}</b>\n"
        f"👤 {ann['author']} | 📅 {ann['date']}\n"
        f"🔗 <a href='{ann['url']}'>Ninova'da Oku</a>\n\n"
        f"{escape_html(content)}"
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
            for key, val in grades.items():
                score = val.get("not", "?")
                weight = val.get("agirlik", "")
                weight_str = f" (%{weight})" if weight else ""
                response += f"▫️ {key}: <b>{score}</b>{weight_str}\n"

                details = val.get("detaylar", {})
                detail_lines = []
                if "class_avg" in details:
                    detail_lines.append(f"Ort: {details['class_avg']}")
                if "std_dev" in details:
                    detail_lines.append(f"Std: {details['std_dev']}")
                if "rank" in details:
                    detail_lines.append(f"Sıra: {details['rank']}")

                if detail_lines:
                    response += f"   <i>└ {', '.join(detail_lines)}</i>\n"

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
                    types.InlineKeyboardButton(
                        f"🔹 {title}", callback_data=f"ann_{course_idx}_{i}"
                    )
                )

    markup.add(
        types.InlineKeyboardButton("↩️ Geri Dön", callback_data=f"crs_{course_idx}")
    )
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=response,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu(call):
    chat_id = str(call.message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})
    markup = types.InlineKeyboardMarkup()
    for i, (url, data) in enumerate(user_grades.items()):
        markup.add(
            types.InlineKeyboardButton(
                f"📚 {data.get('course_name', 'Bilinmeyen Ders')}",
                callback_data=f"crs_{i}",
            )
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
    bot.answer_callback_query(call.id, "Dosya hazırlanıyor...")
    bot.send_chat_action(chat_id, "upload_document")

    users = load_all_users()
    user_info = users.get(chat_id, {})
    username = user_info.get("username")
    password = decrypt_password(user_info.get("password", ""))

    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = requests.Session()
        USER_SESSIONS[chat_id].headers.update(HEADERS)

    session = USER_SESSIONS[chat_id]
    filepath = download_file(
        session,
        file_data["url"],
        file_data["name"],
        chat_id=chat_id,
        username=username,
        password=password,
    )

    if filepath:
        # Dosya adının son kısmını al (uzantı bilgisi için)
        display_name = (
            file_data["name"].split("/")[-1]
            if "/" in file_data["name"]
            else file_data["name"]
        )
        send_telegram_document(
            chat_id,
            filepath,
            caption=f"{get_file_icon(display_name)} {display_name}",
        )
    else:
        bot.send_message(chat_id, "❌ Dosya indirilemedi.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dir_"))
def handle_folder_navigation(call):
    parts = call.data.split("_", 2)
    course_idx = int(parts[1])
    path_str = parts[2] if len(parts) > 2 else ""
    bot.answer_callback_query(call.id)
    show_file_browser(
        str(call.message.chat.id), call.message.message_id, course_idx, path_str
    )


@bot.callback_query_handler(func=lambda call: call.data == "lv_yes")
def handle_leave_confirm(call):
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


@bot.callback_query_handler(func=lambda call: call.data == "lv_no")
def handle_leave_cancel(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Vazgeçildi, sistemde kalmaya devam ediyorsunuz.",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def handle_course_delete_any(call):
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
        urls = users.get(chat_id, {}).get("urls", [])
        if idx < len(urls):
            del urls[idx]
            save_all_users(users)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="✅ Ders başarıyla silindi.",
            )
    elif call.data == "del_no":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Silme işlemi iptal edildi.",
        )
