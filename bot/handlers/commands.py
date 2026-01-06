import requests
from telebot import types
from datetime import datetime
import bot.core as bc  # LAST_CHECK_TIME için gerekli (isim çakışmasını önlemek için 'as bc')
from bot.core import (
    bot_instance as bot,
    get_check_callback,
    START_TIME,
)
from bot.keyboards import build_main_keyboard
from core.config import load_all_users, HEADERS, USER_SESSIONS
from core.utils import (
    load_saved_grades,
    update_user_data,
    escape_html,
    decrypt_password,
)
from core.logic import predict_course_performance
from ninova import login_to_ninova, get_user_courses


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    update_user_data(message.chat.id, "chat_id", str(message.chat.id))
    help_text = (
        "👋 <b>Ninova Not Takipçisi Botuna Hoş Geldiniz!</b>\n\n"
        "Notlarınızı takip edebilmek için lütfen aşağıdaki adımları sırasıyla uygulayın:\n\n"
        "1️⃣ <b>Kullanıcı Adı:</b> /username komutu ile Ninova kullanıcı adınızı girin.\n"
        "2️⃣ <b>Şifre:</b> /password komutu ile Ninova şifrenizi girin.\n"
        "3️⃣ <b>Ders Ekleme:</b> /otoders ile tüm dersleri otomatik ekleyin veya /ekle ile manuel ekleyin.\n\n"
        "🔍 <b>Diğer Komutlar:</b>\n"
        "/notlar - Kayıtlı tüm notları ve ortalamaları listeler\n"
        "/odevler - Yaklaşan ödevleri ve teslim durumlarını gösterir\n"
        "/dersler - İnteraktif ders menüsü (Dosya/Ödev/Not)\n"
        "/search &lt;kelime&gt; - Duyurularda kelime arama yapar\n"
        "/otoders - Tüm dersleri Ninova'dan otomatik çeker ve ekler\n"
        "/liste - Takip ettiğiniz ders linklerini gösterir\n"
        "/sil - Takip edilen bir dersi listeden kaldırır\n"
        "/kontrol - Notları şimdi manuel olarak kontrol eder\n"
        "/durum - Sistemin çalışma ve takip durumunu gösterir\n"
        "/ayril - Sistemden kaydınızı ve verilerinizi siler\n\n"
        "⚠️ <i>Not: Bilgileriniz güvenli bir şekilde sadece Ninova girişi için kullanılır.</i>"
    )
    bot.reply_to(
        message, help_text, parse_mode="HTML", reply_markup=build_main_keyboard()
    )


@bot.message_handler(commands=["menu"])
def show_menu(message):
    bot.send_message(
        message.chat.id,
        "📋 Komut menüsü açıldı. Bir komut seçin veya yazmaya başlayın.",
        reply_markup=build_main_keyboard(),
    )


@bot.message_handler(commands=["notlar"])
def list_grades(message):
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz kayıtlı not bulunamadı.")
        return

    response = "📊 <b>Mevcut Notlarınız:</b>\n\n"
    for url, data in user_grades.items():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        grades = data.get("grades", {})
        response += f"📚 <b>{course_name}</b>\n"
        if not grades:
            response += "<i>Henüz not girilmemiş.</i>\n"
        else:
            response += f"<code>{'Sınav':<15} | {'%':>3} | {'Not':>5}</code>\n"
            response += f"<code>{'-' * 28}</code>\n"
            for exam, info in grades.items():
                w_raw = (
                    info.get("agirlik", "").replace("%", "").replace(",", ".").strip()
                )
                try:
                    w_val = float(w_raw)
                    w = f"{w_val:g}"
                except Exception:
                    w = ""
                w_disp = f"{w:>3}"
                response += (
                    f"<code>{exam[:15]:<15} | {w_disp} | {info['not']:>5}</code>"
                )

                # Ekstra detaylar
                details = info.get("detaylar", {})
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

            perf = predict_course_performance(data)
            if perf and "current_avg" in perf:
                weight_info = (
                    f" (%{perf['total_weight_entered']:.0f})"
                    if perf.get("total_weight_entered", 0) > 0
                    else ""
                )
                response += f"📈 <b>Ortalama:</b> <code>{perf['current_avg']:.2f}</code>{weight_info}\n"
                if perf.get("class_avg") is not None:
                    response += (
                        f"👥 <b>Sınıf Ort:</b> <code>{perf['class_avg']:.2f}</code>\n"
                    )
                if "predicted_letter" in perf:
                    response += (
                        f"🎯 <b>Tahmin:</b> <code>{perf['predicted_letter']}</code>\n"
                    )
        response += "\n"

    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            bot.send_message(message.chat.id, response[x : x + 4000], parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, response, parse_mode="HTML")


@bot.message_handler(commands=["odevler"])
def list_assignments(message):
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz kayıtlı veri bulunamadı.")
        return

    response = "📅 <b>Ödev Durumları:</b>\n\n"
    for url, data in user_grades.items():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        assignments = data.get("assignments", [])
        response += f"📚 <b>{course_name}</b>\n"
        if not assignments:
            response += "<i>Ödev bulunamadı.</i>\n"
        else:
            for target_assign in assignments:
                status = "✅" if target_assign.get("is_submitted") else "❌"
                response += f"{status} <a href='{target_assign['url']}'>{target_assign['name']}</a>\n"
                response += (
                    f"└ ⏳ Son Teslim: <code>{target_assign['end_date']}</code>\n"
                )
        response += "\n"

    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            bot.send_message(message.chat.id, response[x : x + 4000], parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, response, parse_mode="HTML")


@bot.message_handler(commands=["ders", "dersler"])
def interactive_menu(message):
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(
            message, "Henüz takip ettiğiniz ders yok. /otoders ile ekleyebilirsiniz."
        )
        return

    markup = types.InlineKeyboardMarkup()
    for i, (url, data) in enumerate(user_grades.items()):
        course_name = data.get("course_name", "Bilinmeyen Ders")
        markup.add(
            types.InlineKeyboardButton(f"📚 {course_name}", callback_data=f"crs_{i}")
        )

    bot.send_message(
        message.chat.id,
        "📖 <b>Takip Ettiğiniz Dersler:</b>\nDetay görmek için bir ders seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(commands=["search"])
def search_announcements(message):
    chat_id = str(message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(
            message,
            "❌ Lütfen aramak istediğiniz kelimeyi belirtin.\n\nKullanım: <code>/search kelime</code>",
            parse_mode="HTML",
        )
        return

    search_term = parts[1].strip().lower()
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz kayıtlı ders bulunamadı.")
        return

    bot.send_message(
        message.chat.id,
        f"🔍 <b>'{escape_html(search_term)}'</b> için arama yapılıyor...",
        parse_mode="HTML",
    )
    results = []

    for url, data in user_grades.items():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        announcements = data.get("announcements", [])
        for announcement in announcements:
            title = announcement.get("title", "").lower()
            content = announcement.get("content", "").lower()
            if search_term in title or search_term in content:
                results.append(
                    {
                        "course": course_name,
                        "title": announcement.get("title", ""),
                        "content": announcement.get("content", ""),
                        "date": announcement.get("date", ""),
                        "url": announcement.get("url", ""),
                    }
                )

    if not results:
        bot.send_message(
            message.chat.id,
            f"😔 '<b>{escape_html(search_term)}</b>' için sonuç bulunamadı.",
            parse_mode="HTML",
        )
        return

    response = f"🔍 <b>Arama Sonuçları:</b> '{escape_html(search_term)}'\n💡 <b>{len(results)}</b> sonuç bulundu\n\n"
    for i, result in enumerate(results, 1):
        response += f"<b>{i}. {escape_html(result['course'])}</b>\n📢 <b>{escape_html(result['title'])}</b>\n"
        if result["date"]:
            response += f"📅 {escape_html(result['date'])}\n"
        content = result["content"]
        if len(content) > 150:
            content = content[:150] + "..."
        response += f"💬 {escape_html(content)}\n"
        if result["url"]:
            response += f"🔗 <a href='{result['url']}'>Duyuruyu Görüntüle</a>\n"
        response += "\n"
        if len(response) > 3500:
            bot.send_message(
                message.chat.id,
                response,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            response = ""
    if response:
        bot.send_message(
            message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True
        )


@bot.message_handler(commands=["kontrol"])
def manual_check(message):
    bot.reply_to(message, "🔄 Kontrol başlatılıyor, lütfen bekleyin...")
    cb = get_check_callback()
    if cb:
        cb()
        bot.send_message(message.chat.id, "✅ Kontrol tamamlandı.")
    else:
        bot.send_message(message.chat.id, "❌ Kontrol sistemi hazır değil.")


@bot.message_handler(commands=["otoders"])
def auto_add_courses(message):
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_info = users.get(chat_id, {})
    username = user_info.get("username")
    password = decrypt_password(user_info.get("password", ""))

    if not username or not password:
        bot.reply_to(
            message,
            "❌ Kullanıcı adı veya şifre eksik! Lütfen önce /username ve /password ile ayarlarınızı yapın.",
        )
        return

    bot.reply_to(message, "⏳ Ninova'ya giriş yapılıyor ve dersleriniz taranıyor...")

    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = requests.Session()
        USER_SESSIONS[chat_id].headers.update(HEADERS)

    session = USER_SESSIONS[chat_id]
    if login_to_ninova(session, chat_id, username, password):
        courses = get_user_courses(session)
        if not courses:
            bot.send_message(
                message.chat.id, "❌ Hiç aktif ders bulunamadı veya bir hata oluştu."
            )
            return

        current_urls = user_info.get("urls", [])
        added_count = 0
        new_urls = list(current_urls)
        response = "✅ <b>Dersleriniz Bulundu:</b>\n\n"
        for course in courses:
            name, url = course["name"], course["url"]
            if url not in new_urls:
                new_urls.append(url)
                added_count += 1
                response += f"➕ <b>{name}</b>\n<code>{url}</code>\n\n"
            else:
                response += f"🔹 <b>{name}</b> (Zaten listede)\n\n"

        if added_count > 0:
            update_user_data(chat_id, "urls", new_urls)
            response += f"🎉 <b>{added_count}</b> yeni ders başarıyla eklendi!\n\n🔄 Yeni dersler için kontrol başlatılıyor..."
        else:
            response += "ℹ️ Yeni eklenecek ders bulunamadı."

        if len(response) > 4000:
            for x in range(0, len(response), 4000):
                bot.send_message(
                    message.chat.id, response[x : x + 4000], parse_mode="HTML"
                )
        else:
            bot.send_message(message.chat.id, response, parse_mode="HTML")

        cb = get_check_callback()
        if added_count > 0 and cb:
            try:
                cb()
                bot.send_message(
                    message.chat.id, "✅ Yeni dersler için kontrol tamamlandı."
                )
            except Exception:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Kontrol başlatılırken bir hata oluştu. /kontrol ile tekrar deneyin.",
                )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Giriş başarısız! Lütfen kullanıcı adı ve şifrenizi kontrol edin.",
        )


@bot.message_handler(commands=["ekle"])
def add_course(message):
    args = message.text.split()
    if len(args) < 2 or "ninova.itu.edu.tr" not in args[1]:
        bot.reply_to(
            message,
            "❌ Lütfen geçerli bir Ninova ders linki girin.\nÖrn: <code>/ekle https://ninova.itu.edu.tr/Sinif/123.456</code>",
            parse_mode="HTML",
        )
        return

    url = args[1].split("?")[0].strip()
    # Alt sayfa varsa temizle, base URL olarak sakla
    for suffix in ["/Notlar", "/Duyurular", "/Odevler", "/SinifDosyalari"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break

    chat_id = str(message.chat.id)
    users = load_all_users()
    user_urls = users.get(chat_id, {}).get("urls", [])

    if url in user_urls:
        bot.reply_to(message, "⚠️ Bu ders zaten listenizde.")
        return

    user_urls.append(url)
    update_user_data(chat_id, "urls", user_urls)
    bot.reply_to(message, "✅ Ders başarıyla eklendi. İlk kontrol yapılıyor...")

    cb = get_check_callback()
    if cb:
        try:
            cb()
        except Exception:
            pass


@bot.message_handler(commands=["sil"])
def delete_course(message):
    chat_id = str(message.chat.id)
    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.reply_to(message, "Henüz takip ettiğiniz ders yok.")
        return

    markup = types.InlineKeyboardMarkup()
    for i, (url, data) in enumerate(user_grades.items()):
        course_name = data.get("course_name", "Bilinmeyen Ders")
        markup.add(
            types.InlineKeyboardButton(f"❌ {course_name}", callback_data=f"del_{i}")
        )

    bot.send_message(
        message.chat.id, "🗑️ Silmek istediğiniz dersi seçin:", reply_markup=markup
    )


@bot.message_handler(commands=["liste"])
def list_urls(message):
    chat_id = str(message.chat.id)
    users = load_all_users()
    urls = users.get(chat_id, {}).get("urls", [])

    if not urls:
        bot.reply_to(message, "Takip ettiğiniz ders bulunamadı.")
        return

    response = "📋 <b>Takip Ettiğiniz Ders Linkleri:</b>\n\n"
    for url in urls:
        response += f"🔗 {url}\n"
    bot.reply_to(message, response, parse_mode="HTML", disable_web_page_preview=True)


@bot.message_handler(commands=["username"])
def set_username(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(
            message,
            "❌ Lütfen kullanıcı adınızı belirtin.\nÖrn: <code>/username mehmet21</code>",
            parse_mode="HTML",
        )
        return
    update_user_data(message.chat.id, "username", parts[1])
    bot.reply_to(
        message,
        f"✅ Kullanıcı adı kaydedildi: <code>{parts[1]}</code>",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["password"])
def set_password(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(
            message,
            "❌ Lütfen şifrenizi belirtin.\nÖrn: <code>/password sifre123</code>",
            parse_mode="HTML",
        )
        return
    update_user_data(message.chat.id, "password", parts[1])
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        "✅ Şifreniz güvenli bir şekilde kaydedildi ve güvenlik için mesajınız silindi.",
    )


@bot.message_handler(commands=["durum"])
def show_status(message):
    chat_id = str(message.chat.id)
    users = load_all_users()
    user_info = users.get(chat_id, {})

    # İstatistikler
    total_users = len(users)
    total_courses_tracked = sum(len(u.get("urls", [])) for u in users.values())

    course_count = len(user_info.get("urls", []))
    username = user_info.get("username")
    user_display = username if username else "❌"
    has_pass = "✅" if user_info.get("password") else "❌"

    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)

    last_val = bc.LAST_CHECK_TIME
    last_check_str = last_val.strftime("%H:%M:%S") if last_val else "Henüz yapılmadı"

    status = (
        "🤖 <b>Sistem Durumu</b>\n\n"
        f"⏱ <b>Uptime:</b> {hours}s {minutes}dk\n"
        f"🔄 <b>Son Kontrol:</b> {last_check_str}\n"
        f"👥 <b>Toplam Kullanıcı:</b> {total_users}\n"
        f"📚 <b>Toplam Takip Edilen Ders:</b> {total_courses_tracked}\n\n"
        "👤 <b>Hesap Bilgileriniz:</b>\n"
        f"└ Kullanıcı Adı: {user_display}\n"
        f"└ Şifre: {has_pass}\n"
        f"└ Takip Edilen Ders: <b>{course_count}</b>"
    )
    bot.reply_to(message, status, parse_mode="HTML")


@bot.message_handler(commands=["ayril"])
def leave_system(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Evet, Verilerimi Sil", callback_data="leave_confirm"
        ),
        types.InlineKeyboardButton("Hayır, Vazgeç", callback_data="leave_cancel"),
    )
    bot.reply_to(
        message,
        "⚠️ <b>DİKKAT!</b>\n\nSistemden ayrılmak üzeresiniz. Tüm kayıtlı verileriniz ve takip listeniz kalıcı olarak silinecek. Onaylıyor musunuz?",
        reply_markup=markup,
        parse_mode="HTML",
    )
