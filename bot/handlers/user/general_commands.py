"""
Genel kullanıcı komutları.
"""

import threading
from datetime import datetime

from telebot import types

import bot.instance as bc
from bot.instance import START_TIME
from bot.instance import bot_instance as bot
from bot.keyboards import (
    build_cancel_keyboard,
    build_main_keyboard,
    build_user_menu_keyboard,
)
from common.config import load_all_users
from common.utils import escape_html, load_saved_grades, split_long_message, update_user_data
from services.calendar.itu_calendar import ITUCalendarService

# ... (omitted)


@bot.message_handler(func=lambda message: message.text == "🔙 Geri")
def go_back_main(message):
    """
    Ana menüye dönüş sağlar.
    """
    bot.send_message(
        message.chat.id,
        "Menüye dönüldü.",
        reply_markup=build_main_keyboard(),
    )


def _is_cancel_text(text: str) -> bool:
    """Check if the message text indicates a cancel action."""
    if not text:
        return False
    t = text.strip().lower()
    return "iptal" in t or "cancel" in t or "⛔" in text


@bot.message_handler(func=lambda message: message.text == "👤 Kullanıcı")
def show_user_menu(message):
    """
    Kullanıcı ayarları alt menüsünü gösterir.
    """
    bot.send_message(
        message.chat.id,
        "👤 Kullanıcı Menüsü:",
        reply_markup=build_user_menu_keyboard(),
    )


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """
    Kullanıcıya karşılama mesajını ve yardım metnini gönderir.
    Güvenlik ve şeffaflık vurgusu yapar.
    """
    update_user_data(message.chat.id, "chat_id", str(message.chat.id))

    welcome_text = (
        "👋 <b>Ninova Not Takipçisi'ne Hoş Geldiniz!</b>\n\n"
        "Ben, İTÜ'lüler için geliştirilmiş <b>açık kaynaklı</b> bir yardımcı botum.\n"
        "Amacım; notlarınızı, ödevlerinizi ve kampüs gündemini en hızlı şekilde size ulaştırmak.\n\n"
        "🛡️ <b>Güvenlik & Gizlilik</b>\n"
        "Ninova verilerinize erişebilmek için giriş yapmaya ihtiyacım var. Ancak endişelenmeyin:\n"
        "• Şifreniz <b>AES-256</b> standardı ile şifrelenir.\n"
        "• Verileriniz sadece bu sunucuda <b>şifrelenmiş</b> olarak saklanır, 3. taraflarla paylaşılmaz.\n"
        "• İstediğiniz zaman <code>👤 Kullanıcı -> 🚪 Ayrıl</code> menüsünden tüm verilerinizi silebilirsiniz.\n"
        "• Kodlarım tamamen şeffaftır, inceleyebilir veya kendi bilgisayarınızda çalıştırabilirsiniz.\n\n"
        "🚀 <b>Başlarken:</b>\n"
        "1. Aşağıdaki 'Sıkça Sorulan Sorular' butonuna tıklayarak aklınızdaki soruları giderin.\n"
        "2. 'Kaynak Kodu' butonundan GitHub'da kodlarımı inceleyin.\n"
        "3. Hazır hissettiğinizde '👤 Kullanıcı' menüsünden itü kullanıcı adı ve şifrenizi girerek giriş yapın.\n"
        "4. '🤖 Otoders' ile derslerinizi senkronize edin ve tüm güzel özellikleri keşfedin!\n"
    )

    # Inline Keyboard for Trust
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_faq = types.InlineKeyboardButton(
        "❓ Sıkça Sorulan Sorular / Güvenlik", callback_data="faq_security"
    )
    btn_source = types.InlineKeyboardButton(
        "💻 Kaynak Kodu (GitHub)", url="https://github.com/farukyo/ninovaNotifier"
    )
    markup.add(btn_faq, btn_source)

    # Send Welcome with Inline Actions
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )

    # Send Main Menu separately to ensure it persists
    bot.send_message(
        message.chat.id,
        "👇 İşlemleriniz için aşağıdaki menüyü kullanabilirsiniz:",
        reply_markup=build_main_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "faq_security")
def callback_faq(call):
    """FAQ butonuna basıldığında tetiklenir."""
    # Sadece mesajı güncelleme veya yeni mesaj atma
    # Burada yeni mesaj atarak temiz bir görünüm sağlıyoruz
    show_faq(call.message)
    # Callback'i cevapla (loading dairesini kaldırır)
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=["faq"])
def show_faq(message):
    """
    Sıkça sorulan soruları ve güvenlik detaylarını gösterir.
    """
    faq_text = (
        "❓ <b>Sıkça Sorulan Sorular & Güvenlik</b>\n\n"
        "<b>S: Şifrem güvende mi?</b>\n"
        "C: Evet. Şifrenizi veritabanına kaydetmeden önce <b>AES-256</b> ile şifreliyorum. Anahtar sadece sunucuda bulunur.\n\n"
        "<b>S: Neden şifremi istiyorsun?</b>\n"
        "C: Senin adına Ninova'ya girip notlarını vs. çekebilmesi için botun şifrene ihtiyacı var. Maalesef İTÜ'nün sunduğu başka bir erişim yöntemi (API) yok.\n\n"
        "<b>S: Verilerimi kimler görebilir?</b>\n"
        "C: Şifren şifreli olduğu için ben dahil kimse veritabanını açıp şifreni okuyamaz. Benim bilgilerim:\n"
        "Kullanıcı Adım: <code>olusan23</code>\n"
        "Şifrem (Veritabanındaki Hali): <code>gAAAAABpaSBCXrSlCegdWvVc3Q-Lpf1Wi0b8kBE49poP7oWKicpU_UeKlW4bXqEZwvz6GDwnsX8VG05LSER-x_wz39q6y2xPLA==</code>\n"
        "<b>S: Sana güvenmiyorum!</b>\n"
        "C: En doğal hakkın, bana güvenme koda güven. Aşağıdaki butondan tüm kaynak kodlarımı inceleyebilirsin. Hatta istersen botu kendi bilgisayarında çalıştırabilirsin, o zaman verilerin tamamen senin kontrolünde olur.\n\n"
        "<b>S: Verilerimi silebilir miyim?</b>\n"
        "C: Tabii ki. <code>/ayril</code> komutunu gönderdiğin an tüm bilgilerini (kullanıcı adın, şifren, ayarların) saniyeler içinde kalıcı olarak silerim."
    )

    # Altına tekrar kaynak kodu butonu ekleyelim
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "💻 GitHub Kaynak Kodu", url="https://github.com/farukyo/ninovaNotifier"
        )
    )

    bot.send_message(
        message.chat.id,
        faq_text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


@bot.message_handler(func=lambda message: message.text == "⛔ İptal")
def handle_cancel_button(message):
    """Handle cancel button press - clears any pending input and returns to menu."""
    chat_id = message.chat.id
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
    if _is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ Arama iptal edildi.", reply_markup=build_main_keyboard())
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

    for _url, data in user_grades.items():
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
        bot.send_message(chat_id, response, parse_mode="HTML", disable_web_page_preview=True)


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
        types.InlineKeyboardButton("Evet, Verilerimi Sil", callback_data="leave_confirm"),
        types.InlineKeyboardButton("Hayır, Vazgeç", callback_data="leave_cancel"),
    )
    bot.reply_to(
        message,
        "⚠️ <b>DİKKAT!</b>\n\nSistemden ayrılmak üzeresiniz. Tüm kayıtlı verileriniz ve takip listeniz kalıcı olarak silinecek. Onaylıyor musunuz?",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(func=lambda message: message.text == "📆 Akademik Takvim")
def show_academic_calendar(message):
    """
    İTÜ Akademik Takvimden güncel bilgileri çeker ve gösterir.
    Geçmiş 5, Gelecek 10 satır kuralına göre filtreleme yapar.
    """
    bot.reply_to(message, "🔄 Akademik takvim verileri çekiliyor...")

    def run_fetch():
        try:
            data = ITUCalendarService.get_filtered_calendar()
            chunks = split_long_message(data)
            for chunk in chunks:
                bot.send_message(message.chat.id, chunk, parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Hata oluştu: {str(e)}")

    threading.Thread(target=run_fetch, daemon=True).start()
