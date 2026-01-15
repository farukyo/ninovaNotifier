"""
Ders yönetimi komutları.
"""

import threading

import requests
from telebot import types

from bot.instance import bot_instance as bot
from common.config import HEADERS, USER_SESSIONS, load_all_users
from common.utils import decrypt_password, load_saved_grades, split_long_message, update_user_data
from services.ninova import get_user_courses, login_to_ninova


@bot.message_handler(func=lambda message: message.text == "📖 Dersler")
def interactive_menu(message):
    """
    Etkileşimli ders menüsünü başlatır.

    Kullanıcı ders seçip detaylara (not, ödev, dosya, duyuru) erişebilir.
    Her ders için buton oluşturulur.

    :param message: Kullanıcıdan gelen /ders veya /dersler komutu
    """
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz takip ettiğiniz ders yok. /otoders ile ekleyebilirsiniz.")
        return

    markup = types.InlineKeyboardMarkup()
    for i, (_url, data) in enumerate(user_grades.items()):
        course_name = data.get("course_name", "Bilinmeyen Ders")
        markup.add(types.InlineKeyboardButton(f"📚 {course_name}", callback_data=f"crs_{i}"))

    # Add general control button
    markup.add(types.InlineKeyboardButton("🔄 Tümünü Kontrol Et", callback_data="global_kontrol"))
    # Add Manual Course Menu button
    markup.add(
        types.InlineKeyboardButton("📝 Manuel Ders Yönetimi", callback_data="manual_menu_open")
    )

    bot.send_message(
        message.chat.id,
        "📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(commands=["otoders"])
def user_otoders_command(message):
    """
    Kullanıcı düzeyinde otomatik ders keşfi.

    Bu komut sadece çağıran kullanıcının Ninova hesabına bağlanır,
    ders listesini çeker ve yeni dersleri ekler.
    """
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id)

    if not user_data:
        bot.reply_to(
            message,
            "⚠️ Kullanıcı bilgileri bulunamadı. Lütfen önce kullanıcı adınızı ve şifrenizi ayarlayın.",
        )
        return

    username = user_data.get("username")
    password = decrypt_password(user_data.get("password", ""))

    if not username or not password:
        bot.reply_to(
            message,
            "⚠️ Lütfen önce kullanıcı adınızı ve şifrenizi ayarlayın.",
        )
        return

    bot.reply_to(message, "🔄 Ninova'ya bağlanılıyor ve aktif dersler taranıyor...")

    def run_update():
        try:
            USER_SESSIONS[chat_id] = requests.Session()
            USER_SESSIONS[chat_id].headers.update(HEADERS)
            session = USER_SESSIONS[chat_id]

            if not login_to_ninova(session, chat_id, username, password):
                bot.send_message(
                    chat_id,
                    "❌ Ninova'ya giriş yapılamadı. Bilgilerinizi kontrol edin.",
                )
                return

            courses = get_user_courses(session)
            if not courses:
                bot.send_message(chat_id, "❌ Aktif ders bulunamadı veya çekilemedi.")
                return

            all_grades = load_saved_grades()
            user_grades = all_grades.get(chat_id, {})
            current_urls = set(user_data.get("urls", []))

            already_added = []
            newly_added = []
            new_urls_list = list(current_urls)

            for course in courses:
                course_url = course.get("url")
                course_name = course.get("name", "Bilinmeyen Ders")

                if not course_url:
                    continue

                if course_url in user_grades:
                    already_added.append(course_name)
                elif course_url in current_urls:
                    newly_added.append({"name": course_name, "url": course_url})
                else:
                    newly_added.append({"name": course_name, "url": course_url})
                    new_urls_list.append(course_url)

            update_user_data(chat_id, "urls", new_urls_list)

            response = "📊 <b>Ders Tarama Sonucu</b>\n\n"

            if already_added:
                response += "✅ <b>Zaten Ekli Dersler:</b>\n"
                for name in already_added:
                    response += f"  • {name}\n"
                response += "\n"

            if newly_added:
                response += "✨ <b>Yeni Eklenen Dersler:</b>\n"
                for c in newly_added:
                    response += f"  ➕ {c['name']}\n"
                response += "\n🔄 Yeni dersler için kontrol başlatılıyor...\n"
            else:
                response += "ℹ️ Yeni eklenecek ders bulunamadı.\n"

            bot.send_message(chat_id, response, parse_mode="HTML")

            if newly_added:
                from main import check_user_updates

                result = check_user_updates(chat_id)
                if result.get("success"):
                    bot.send_message(
                        chat_id,
                        "✅ <b>Kontrol tamamlandı!</b>\nYeni derslerinizin not, ödev, dosya ve duyuru bilgileri alındı.",
                        parse_mode="HTML",
                    )
                else:
                    bot.send_message(
                        chat_id,
                        f"⚠️ Kontrol sırasında hata: {result.get('message', 'Bilinmeyen hata')}",
                        parse_mode="HTML",
                    )

        except Exception as e:
            bot.send_message(chat_id, f"❌ Hata oluştu: {str(e)}")

    threading.Thread(target=run_update, daemon=True).start()


@bot.message_handler(func=lambda message: message.text == "🤖 Oto Ders")
def auto_add_courses(message):
    """
    Ninova'ya bağlanarak kullanıcının tüm derslerini otomatik olarak bulur ve ekler.
    """
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_info = users.get(chat_id, {})
    username = user_info.get("username")
    password = decrypt_password(user_info.get("password", ""))

    if not username or not password:
        bot.reply_to(
            message,
            "❌ Kullanıcı adı veya şifre eksik! Lütfen önce 👤 Kullanıcı Adı ve 🔐 Şifre butonları ile ayarlarınızı yapın.",
        )
        return

    bot.reply_to(message, "⏳ Ninova'ya giriş yapılıyor ve dersleriniz taranıyor...")

    def run_auto_add():
        try:
            if chat_id not in USER_SESSIONS:
                USER_SESSIONS[chat_id] = requests.Session()
                USER_SESSIONS[chat_id].headers.update(HEADERS)

            session = USER_SESSIONS[chat_id]
            if login_to_ninova(session, chat_id, username, password):
                courses = get_user_courses(session)
                if not courses:
                    bot.send_message(chat_id, "❌ Hiç aktif ders bulunamadı veya bir hata oluştu.")
                    return

                all_grades = load_saved_grades()
                user_grades = all_grades.get(chat_id, {})
                current_urls = set(user_info.get("urls", []))

                already_in_data = []
                newly_added = []
                new_urls_list = list(current_urls)

                for course in courses:
                    name, url = course["name"], course["url"]

                    if url in user_grades:
                        already_in_data.append(name)
                    elif url in current_urls:
                        newly_added.append({"name": name, "url": url})
                    else:
                        newly_added.append({"name": name, "url": url})
                        new_urls_list.append(url)

                if new_urls_list != list(current_urls):
                    update_user_data(chat_id, "urls", new_urls_list)

                response = "📊 <b>Ders Tarama Sonucu</b>\n\n"

                if already_in_data:
                    response += "✅ <b>Zaten Ekli Dersler:</b>\n"
                    for name in already_in_data:
                        response += f"  • {name}\n"
                    response += "\n"

                if newly_added:
                    response += "✨ <b>Yeni Eklenen Dersler:</b>\n"
                    for c in newly_added:
                        response += f"  ➕ {c['name']}\n"
                    response += "\n🔄 Yeni dersler için kontrol başlatılıyor...\n"
                else:
                    response += "ℹ️ Yeni eklenecek ders bulunamadı.\n"

                chunks = split_long_message(response)
                for chunk in chunks:
                    bot.send_message(chat_id, chunk, parse_mode="HTML")

                if newly_added:
                    from main import check_user_updates

                    # İlk tarama sessiz modda yapılır (spam önleme)
                    result = check_user_updates(chat_id, silent=True)
                    
                    if result.get("success"):
                        bot.send_message(
                            chat_id,
                            "✅ <b>Kurulum Tamamlandı!</b>\n"
                            "Derslerinizin verileri başarıyla senkronize edildi.\n"
                            "Bundan sonraki <b>yeni</b> not, ödev ve duyurular için bildirim alacaksınız.",
                            parse_mode="HTML",
                        )
                    else:
                        bot.send_message(
                            chat_id,
                            f"⚠️ Kontrol sırasında hata: {result.get('message', 'Bilinmeyen hata')}",
                            parse_mode="HTML",
                        )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Giriş başarısız! Lütfen kullanıcı adı ve şifrenizi kontrol edin.",
                )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Hata oluştu: {str(e)}")

    threading.Thread(target=run_auto_add, daemon=True).start()


def add_course(message):
    """Manuel olarak Ninova ders linki ekler.

    Kullanım: /ekle <url>
    """
    args = message.text.split()
    if len(args) < 2 or "ninova.itu.edu.tr" not in args[1]:
        bot.reply_to(
            message,
            "❌ Lütfen geçerli bir Ninova ders linki girin.\nÖrn: <code>/ekle https://ninova.itu.edu.tr/Sinif/123.456</code>",
            parse_mode="HTML",
        )
        return

    url = args[1].split("?")[0].strip()
    for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break

    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])

    if url in urls:
        bot.reply_to(
            message,
            "⚠️ Bu ders zaten takip ediliyor.",
        )
        return

    urls.append(url)
    update_user_data(chat_id, "urls", urls)
    bot.reply_to(
        message,
        f"✅ Ders başarıyla eklendi!\n<code>{url}</code>",
        parse_mode="HTML",
    )


def list_courses(message):
    """
    Kullanıcının takip ettiği dersleri listeler.
    """
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not urls:
        bot.reply_to(message, "❌ Takip ettiğiniz ders bulunamadı.")
        return

    response = "📋 <b>Takip Ettiğiniz Dersler:</b>\n\n"
    for i, url in enumerate(urls, 1):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i}")
        response += f"{i}. <b>{course_name}</b>\n<code>{url}</code>\n\n"

    chunks = split_long_message(response)
    for chunk in chunks:
        bot.send_message(message.chat.id, chunk, parse_mode="HTML")


def delete_course(message):
    """
    Kullanıcıdan bir ders seçerek silme menüsünü gösterir.
    """
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_data = users.get(chat_id, {})
    urls = user_data.get("urls", [])
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not urls:
        bot.reply_to(message, "❌ Silinecek ders bulunamadı.")
        return

    markup = types.InlineKeyboardMarkup()
    for i, url in enumerate(urls):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i + 1}")
        display_text = course_name if len(course_name) <= 40 else course_name[:37] + "..."
        markup.add(types.InlineKeyboardButton(f"🗑️ {display_text}", callback_data=f"del_req_{i}"))

    markup.add(types.InlineKeyboardButton("↩️ İptal", callback_data="del_no"))

    bot.send_message(
        chat_id,
        "🗑️ <b>Ders Silme</b>\n\nSilmek istediğiniz dersi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )
