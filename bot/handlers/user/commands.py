import requests
import threading
from telebot import types
from datetime import datetime
import bot.instance as bc  # LAST_CHECK_TIME için gerekli (isim çakışmasını önlemek için 'as bc')
from bot.instance import (
    bot_instance as bot,
    START_TIME,
)
from bot.keyboards import build_main_keyboard, build_manual_menu, build_cancel_keyboard
from common.config import load_all_users, HEADERS, USER_SESSIONS
from common.utils import (
    load_saved_grades,
    update_user_data,
    escape_html,
    decrypt_password,
)
from services.ninova import login_to_ninova, get_user_courses


def _is_cancel_text(text: str) -> bool:
    """Check if the message text indicates a cancel action.

    Returns True for:
    - The cancel button label '⛔ İptal'
    - Typed 'iptal' or 'cancel'
    - Any text containing these words
    """
    if not text:
        return False
    t = text.strip().lower()
    # Accept typed 'iptal' or the button label containing 'iptal' (e.g. '⛔ İptal')
    return "iptal" in t or "cancel" in t or "⛔" in text


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """
    Kullanıcıya karşılama mesajını ve yardım metnini gönderir.
    Kullanıcıyı veritabanında başlatır.
    """
    update_user_data(message.chat.id, "chat_id", str(message.chat.id))
    help_text = (
        "👋 <b>Ninova Not Takipçisi'ne Hoş Geldiniz!</b>\n\n"
        "Notlarınızı takip edebilmek için öncelikle Ninova hesabınızı ekleyin:\n\n"
        "1️⃣ <b>Kullanıcı Adı:</b> '👤 Kullanıcı Adı' butonu ile kullanıcı adınızı ayarlayın.\n"
        "2️⃣ <b>Şifre:</b> '🔐 Şifre' butonu ile şifrenizi gönderin (mesaj otomatik silinir).\n"
        "3️⃣ <b>Ders Ekleme:</b> 🤖 'Oto Ders' ile tüm dersleri ekleyin veya 📝 'Manuel Ders' ile tek tek ekleyin.\n\n"
        "🔎 <b>Hızlı Menü:</b>\n"
        "• 📊 Notlar — Kayıtlı notlarınızı gösterir\n"
        "• 📅 Ödevler — Ödev ve teslim durumları\n"
        "• 📖 Dersler — Ders detay menüsü\n"
        "• 🔍 Ara — Duyurularda arama yapar\n"
        "• 📋 Durum — Bot ve hesap durumunuz\n"
        "• 🚪 Ayrıl — Tüm verilerinizi siler\n\n"
        "ℹ️ <i>Yardım için klavyedeki '❓ Yardım' butonuna basabilirsiniz.</i>"
    )
    bot.reply_to(
        message, help_text, parse_mode="HTML", reply_markup=build_main_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "⛔ İptal")
def handle_cancel_button(message):
    """Handle cancel button press - clears any pending input and returns to menu."""
    chat_id = message.chat.id
    # Clear any registered next step handlers for this chat
    bot.clear_step_handler_by_chat_id(chat_id)
    bot.send_message(
        chat_id,
        "❌ İşlem iptal edildi.",
        reply_markup=build_main_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "❓ Yardım")
def send_help_button(message):
    """Yardım butonuna basıldığında `send_welcome` davranışını tekrarlar."""
    send_welcome(message)


@bot.message_handler(commands=["menu"])
def show_menu(message):
    """
    Kullanıcıya ana menü klavyesini gösterir.

    Tüm mevcut komutları içeren ReplyKeyboard oluşturur.

    :param message: Kullanıcıdan gelen /menu komutu
    """
    bot.send_message(
        message.chat.id,
        "📋 Komut menüsü açıldı. Bir komut seçin veya yazmaya başlayın.",
        reply_markup=build_main_keyboard(),
    )


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
    for url, data in user_grades.items():
        course_name = data.get("course_name", "Bilinmeyen Ders")
        grades = data.get("grades", {})
        response += f"📚 <b>{course_name}</b>\n"
        if not grades:
            response += "<i>Henüz not girilmemiş.</i>\n"
        else:
            response += f"<code>{'Sınav':<15} | {'%':>3} | {'Not':>5}</code>\n"
            response += f"<code>{'-' * 28}</code>\n"

        # Weighted Class Average & Std Calculation
        total_weight = 0.0
        weighted_avg_sum = 0.0
        weighted_var_sum = 0.0
        user_weighted_avg_sum = 0.0
        import math

        for exam, info in grades.items():
            # Parse weight
            w_raw = info.get("agirlik", "").replace("%", "").replace(",", ".").strip()
            try:
                w_val = float(w_raw)
            except ValueError:
                w_val = 0.0

            # Parse details
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
                try:
                    std_dev = float(details["std_dev"].replace(",", "."))
                except ValueError:
                    pass

            # Display logic
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

            # Accumulate for course statistics
            if w_val > 0:
                # Normalize weight: 20% -> 0.20
                w_norm = w_val / 100.0
                total_weight += w_val
                
                # User Average Calculation
                try:
                    user_grade_val = float(str(info['not']).replace(",", "."))
                    user_weighted_avg_sum += w_norm * user_grade_val
                except (ValueError, TypeError):
                    pass
                
                # Class Stats Calculation
                if has_stats:
                    weighted_avg_sum += w_norm * class_avg
                    # Var(aX) = a^2 Var(X)
                    weighted_var_sum += (w_norm * w_norm) * (std_dev * std_dev)

        # Append Course Statistics
        if total_weight > 0:
            c_avg = f"{weighted_avg_sum:.2f}"
            c_std = f"{math.sqrt(weighted_var_sum):.2f}"
            u_avg = f"{user_weighted_avg_sum:.2f}"
            
            response += f"----------------------------\n"
            response += f"📊 <b>Ortalamanız: {u_avg}</b> | Sınıf geneli: Ort: {c_avg}, Std: {c_std} (%{total_weight:g} veriye göre)\n"

        response += "\n"

    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            bot.send_message(message.chat.id, response[x : x + 4000], parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, response, parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text == "📅 Ödevler")
def list_assignments(message):
    """
    Kullanıcının ödevlerini ve teslim durumlarını listeler.
    """
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

    # Add general control button
    markup.add(
        types.InlineKeyboardButton(
            "🔄 Tümünü Kontrol Et", callback_data="global_kontrol"
        )
    )
    # Add Manual Course Menu button
    markup.add(
        types.InlineKeyboardButton(
            "📝 Manuel Ders Yönetimi", callback_data="manual_menu_open"
        )
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
    - Zaten ekliyse "x dersi zaten ekli" mesajı gösterir
    - Yeni ders bulunursa ekler ve /kontrol başlatır
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
            # Yeni oturum oluştur / güncelle
            USER_SESSIONS[chat_id] = requests.Session()
            USER_SESSIONS[chat_id].headers.update(HEADERS)
            session = USER_SESSIONS[chat_id]

            # Giriş yap
            if not login_to_ninova(session, chat_id, username, password):
                bot.send_message(
                    chat_id,
                    "❌ Ninova'ya giriş yapılamadı. Bilgilerinizi kontrol edin.",
                )
                return

            # Dersleri çek
            courses = get_user_courses(session)
            if not courses:
                bot.send_message(chat_id, "❌ Aktif ders bulunamadı veya çekilemedi.")
                return

            # Mevcut verileri yükle
            all_grades = load_saved_grades()
            user_grades = all_grades.get(chat_id, {})
            current_urls = set(user_data.get("urls", []))

            # Sonuç mesajları
            already_added = []
            newly_added = []
            new_urls_list = list(current_urls)

            for course in courses:
                course_url = course.get("url")
                course_name = course.get("name", "Bilinmeyen Ders")

                if not course_url:
                    continue

                # Ders zaten data JSON'da mı?
                if course_url in user_grades:
                    already_added.append(course_name)
                elif course_url in current_urls:
                    # URL'de var ama data'da yok - kontrol edilmeli
                    newly_added.append({"name": course_name, "url": course_url})
                else:
                    # Tamamen yeni ders
                    newly_added.append({"name": course_name, "url": course_url})
                    new_urls_list.append(course_url)

            # URL'leri güncelle
            update_user_data(chat_id, "urls", new_urls_list)

            # Kullanıcıya özet bildir
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

            # Yeni dersler varsa kontrol başlat
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


@bot.message_handler(func=lambda message: message.text == "🔄 Kontrol")
@bot.message_handler(commands=["kontrol"])
def kontrol_command_handler(message):
    """
    Manuel kontrol komudu.
    /kontrol -> Tüm dersleri kontrol eder.
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
            bot.send_message(
                chat_id, f"❌ <b>Hata:</b> {result.get('message')}", parse_mode="HTML"
            )

    threading.Thread(target=run_user_check, daemon=True).start()


@bot.message_handler(func=lambda message: message.text == "🔍 Ara")
def search_announcements(message):
    """
    Ders duyurularında kelime bazlı arama yapar.
    Önce arama kelimesini sorar.
    """
    prompt = bot.send_message(
        message.chat.id,
        "🔍 <b>Arama</b>\n\nHangi metni aramak istiyorsunuz? Lütfen kelimeyi yazın:",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_search_term)


def process_search_term(message):
    """
    Kullanıcının arama kelimesini işler ve arama yapar.
    """
    chat_id = str(message.chat.id)
    # Allow user to cancel the waiting input via button or typed text
    if _is_cancel_text(message.text):
        bot.send_message(
            chat_id, "❌ Arama iptal edildi.", reply_markup=build_main_keyboard()
        )
        return

    search_term = message.text.strip().lower()

    if not search_term:
        bot.send_message(
            chat_id,
            "❌ Geçerli bir arama kelimesi girmediniz. Tekrar deneyin.",
        )
        return

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    if not user_grades:
        bot.send_message(chat_id, "Henüz kayıtlı ders bulunamadı.")
        return

    bot.send_message(
        chat_id,
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
            chat_id,
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
                chat_id,
                response,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            response = ""
    if response:
        bot.send_message(
            chat_id, response, parse_mode="HTML", disable_web_page_preview=True
        )


def manual_check(message):
    """
    Kullanıcı talebiyle manuel not kontrolü başlatır.
    """
    chat_id = str(message.chat.id)
    bot.reply_to(message, "🔄 Kontrol başlatılıyor, lütfen bekleyin...")

    # check_user_updates fonksiyonunu çağır (sadece bu kullanıcıyı kontrol et)
    from main import check_user_updates

    result = check_user_updates(chat_id)

    if result["success"]:
        bot.send_message(chat_id, f"✅ {result['message']}")
    else:
        bot.send_message(chat_id, f"❌ Kontrol başarısız: {result['message']}")


@bot.message_handler(func=lambda message: message.text == "🤖 Oto Ders")
def auto_add_courses(message):
    """
    Ninova'ya bağlanarak kullanıcının tüm derslerini otomatik olarak bulur ve ekler.
    - Zaten data JSON'da olan dersler için "zaten ekli" gösterir
    - Yeni dersler için ekler ve kontrol başlatır
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
                    bot.send_message(
                        chat_id, "❌ Hiç aktif ders bulunamadı veya bir hata oluştu."
                    )
                    return

                # Mevcut verileri kontrol et
                all_grades = load_saved_grades()
                user_grades = all_grades.get(chat_id, {})
                current_urls = set(user_info.get("urls", []))

                already_in_data = []
                newly_added = []
                new_urls_list = list(current_urls)

                for course in courses:
                    name, url = course["name"], course["url"]

                    # Data JSON'da var mı?
                    if url in user_grades:
                        already_in_data.append(name)
                    elif url in current_urls:
                        # URL'de var ama data'da yok - yeni gibi işle
                        newly_added.append({"name": name, "url": url})
                    else:
                        # Tamamen yeni
                        newly_added.append({"name": name, "url": url})
                        new_urls_list.append(url)

                # URL'leri güncelle
                if new_urls_list != list(current_urls):
                    update_user_data(chat_id, "urls", new_urls_list)

                # Sonuç mesajı
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

                if len(response) > 4000:
                    for x in range(0, len(response), 4000):
                        bot.send_message(
                            chat_id, response[x : x + 4000], parse_mode="HTML"
                        )
                else:
                    bot.send_message(chat_id, response, parse_mode="HTML")

                # Yeni dersler varsa kontrol başlat
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

    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            bot.send_message(message.chat.id, response[x : x + 4000], parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, response, parse_mode="HTML")


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
        display_text = (
            course_name if len(course_name) <= 40 else course_name[:37] + "..."
        )
        markup.add(
            types.InlineKeyboardButton(
                f"🗑️ {display_text}", callback_data=f"del_req_{i}"
            )
        )

    markup.add(types.InlineKeyboardButton("↩️ İptal", callback_data="del_no"))

    bot.send_message(
        chat_id,
        "🗑️ <b>Ders Silme</b>\n\nSilmek istediğiniz dersi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(func=lambda message: message.text == " Kullanıcı Adı")
def set_username(message):
    """
    Kullanıcıdan yeni bir mesaj olarak kullanıcı adını ister.
    """
    prompt = bot.send_message(
        message.chat.id,
        "✏️ Lütfen kullanıcı adınızı yazın:",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_username)


def process_username(message):
    chat_id = message.chat.id
    if _is_cancel_text(message.text):
        bot.send_message(
            chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard()
        )
        return

    username = message.text.strip()
    if not username:
        bot.send_message(chat_id, "❌ Geçerli bir kullanıcı adı girmediniz.")
        return

    update_user_data(chat_id, "username", username)
    bot.send_message(
        chat_id,
        f"✅ Kullanıcı adı kaydedildi: <code>{username}</code>",
        parse_mode="HTML",
        reply_markup=build_main_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "🔐 Şifre")
def set_password(message):
    """
    Kullanıcıdan yeni bir mesaj olarak şifreyi ister.
    """
    prompt = bot.send_message(
        message.chat.id,
        "🔒 Lütfen şifrenizi yazın (gönderdiğiniz mesaj otomatik silinecek):",
        reply_markup=build_cancel_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_password)


def process_password(message):
    chat_id = message.chat.id
    # Allow cancel via button
    if _is_cancel_text(message.text):
        bot.send_message(
            chat_id, "❌ İşlem iptal edildi.", reply_markup=build_main_keyboard()
        )
        return

    password = message.text.strip()
    if not password:
        bot.send_message(chat_id, "❌ Geçerli bir şifre girmediniz.")
        return

    update_user_data(chat_id, "password", password)
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    bot.send_message(
        chat_id,
        "✅ Şifreniz güvenli bir şekilde kaydedildi.",
        reply_markup=build_main_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "📋 Durum")
def show_status(message):
    """
    Sistemin ve kullanıcının durumunu gösterir.

    Gösterilen bilgiler:
    - Bot uptime (ne kadar süredir çalışıyor)
    - Son kontrol zamanı
    - Toplam kullanıcı sayısı
    - Toplam takip edilen ders sayısı
    - Kullanıcının hesap bilgileri (kullanıcı adı, şifre durumu, ders sayısı)

    :param message: Kullanıcıdan gelen /durum komutu
    """
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


@bot.message_handler(func=lambda message: message.text == "🚪 Ayrıl")
def leave_system(message):
    """
    Kullanıcının sistemden ayrılması için onay ister.

    Onaylanması durumunda kullanıcının tüm verileri (kullanıcı bilgileri,
    notlar, dersler) kalıcı olarak silinir.

    :param message: Kullanıcıdan gelen /ayril komutu
    """
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
