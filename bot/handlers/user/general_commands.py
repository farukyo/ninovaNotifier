"""
Genel kullanıcı komutları.
"""

import logging
from datetime import datetime

from telebot import types

import bot.instance as bc
from bot.handlers.user.audit import log_user_action
from bot.handlers.user.data_helpers import load_user_grades, load_user_profile
from bot.instance import START_TIME
from bot.instance import bot_instance as bot
from bot.keyboards import (
    build_cancel_keyboard,
    build_extra_features_keyboard,
    build_main_keyboard,
    build_user_menu_keyboard,
)
from bot.utils import is_cancel_text
from common.background_tasks import submit_background_task
from common.config import load_all_users
from common.utils import escape_html, split_long_message, update_user_data
from services.calendar.itu_calendar import ITUCalendarService

logger = logging.getLogger("ninova")


@bot.message_handler(func=lambda message: message.text == "🔙 Geri")
def go_back_main(message):
    """
    Ana menüye dönüş sağlar.
    """
    log_user_action(str(message.chat.id), "go_back_main")
    bot.send_message(
        message.chat.id,
        "Menüye dönüldü.",
        reply_markup=build_main_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "👤 Kullanıcı")
def show_user_menu(message):
    """
    Kullanıcı ayarları alt menüsünü gösterir.
    """
    log_user_action(str(message.chat.id), "show_user_menu")
    bot.send_message(
        message.chat.id,
        "👤 Kullanıcı Menüsü:",
        reply_markup=build_user_menu_keyboard(),
    )


@bot.message_handler(func=lambda message: message.text == "✨ Ekstra")
def show_extra_menu(message):
    """Ekstra özellikler alt menüsünü gösterir."""
    log_user_action(str(message.chat.id), "show_extra_menu")
    bot.send_message(
        message.chat.id,
        "✨ Ekstra Menüsü:",
        reply_markup=build_extra_features_keyboard(),
    )


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """
    Kullanıcıya karşılama mesajını ve yardım metnini gönderir.
    Güvenlik ve şeffaflık vurgusu yapar.
    """
    update_user_data(message.chat.id, "chat_id", str(message.chat.id))
    log_user_action(
        str(message.chat.id),
        "start_command",
        details=f"username={message.from_user.username or 'unknown'}",
    )

    welcome_text = (
        "👋 <b>Ninova Not Takipçisi</b>\n\n"
        "İTÜ Ninova'daki not, ödev ve duyurularınızı takip eden açık kaynaklı bir bot.\n\n"
        "🔐 Şifreniz <b>AES-256</b> ile şifrelenir, 3. taraflarla paylaşılmaz. "
        "İstediğiniz zaman <code>👤 Kullanıcı → 🚪 Ayrıl</code> ile tüm verilerinizi silebilirsiniz.\n\n"
        "Başlamak için <b>👤 Kullanıcı → 🔐 Giriş Yap</b> adımını izleyin."
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
        "❓ <b>Sıkça Sorulan Sorular</b>\n\n"
        "<b>Şifrem güvende mi?</b>\n"
        "Evet. Şifreniz <b>AES-256</b> ile şifrelenerek saklanır; ham haliyle hiç kimse göremez.\n\n"
        "<b>Neden şifre istiyorsun?</b>\n"
        "Bot, Ninova'ya senin adına giriş yaparak verileri çekiyor. İTÜ'nün API'si olmadığından başka yol yok.\n\n"
        "<b>Sana güvenmiyorum.</b>\n"
        "En doğal hakkın. Kaynak kodunu inceleyebilir ya da botu kendi bilgisayarında çalıştırabilirsin.\n\n"
        "<b>Verilerimi silebilir miyim?</b>\n"
        "<code>👤 Kullanıcı → 🚪 Ayrıl</code> ile tüm verilerini anında silerim."
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
    log_user_action(str(chat_id), "cancel")
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
    log_user_action(str(message.chat.id), "search_start")
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
    if is_cancel_text(message.text):
        bot.send_message(chat_id, "❌ Arama iptal edildi.", reply_markup=build_main_keyboard())
        return

    search_term = message.text.strip().lower()

    if not search_term:
        bot.send_message(
            chat_id,
            "❌ Geçerli bir arama kelimesi girmediniz. Tekrar deneyin.",
        )
        return

    user_grades = load_user_grades(chat_id)

    if not user_grades:
        bot.send_message(chat_id, "Henüz kayıtlı ders bulunamadı.")
        return

    bot.send_message(
        chat_id,
        f"🔍 <b>'{escape_html(search_term)}'</b> için arama yapılıyor...",
        parse_mode="HTML",
    )
    results = []

    for data in user_grades.values():
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
    log_user_action(chat_id, "show_status")
    users = load_all_users()
    user_info = load_user_profile(chat_id)

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
    log_user_action(str(message.chat.id), "leave_request")
    bot.reply_to(
        message,
        "⚠️ <b>DİKKAT!</b>\n\nSistemden ayrılmak üzeresiniz. Tüm kayıtlı verileriniz ve takip listeniz kalıcı olarak silinecek. Onaylıyor musunuz?",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(func=lambda message: message.text == "📆 Akademik Takvim")
def show_academic_calendar(message, show_past=False, show_future=False):
    """
    İTÜ Akademik Takvimden güncel bilgileri çeker ve gösterir.
    Varsayılan olarak 10 günlük pencere gösterir (geç geçmiş ve uzak gelecek gizli).

    :param message: Kullanıcıdan gelen mesaj
    :param show_past: Geçmiş etkinlikleri de göster (default: False)
    :param show_future: 10 günden uzak etkinlikleri de göster (default: False)
    """
    log_user_action(
        str(message.chat.id),
        "academic_calendar",
        details=f"show_past={show_past};show_future={show_future}",
    )
    bot.reply_to(message, "🔄 Akademik takvim verileri çekiliyor...")

    def run_fetch():
        try:
            from telebot import types

            data = ITUCalendarService.get_filtered_calendar(
                show_past=show_past, show_future=show_future
            )

            # Check if there are hidden events and create appropriate buttons
            markup = None
            has_hidden_past = "geçmiş etkinlik gizlendi" in data
            has_hidden_future = "uzak gelecek etkinlik gizlendi" in data

            if has_hidden_past or has_hidden_future:
                markup = types.InlineKeyboardMarkup()
                buttons = []

                if has_hidden_past and not show_past:
                    buttons.append(
                        types.InlineKeyboardButton(
                            "📜 Geçmişi Göster", callback_data="show_past_calendar"
                        )
                    )

                if has_hidden_future and not show_future:
                    buttons.append(
                        types.InlineKeyboardButton(
                            "📅 Gelecektekileri Göster",
                            callback_data="show_future_calendar",
                        )
                    )

                if buttons:
                    markup.row(*buttons)

            chunks = split_long_message(data)
            for i, chunk in enumerate(chunks):
                # Only attach button to the last chunk
                if i == len(chunks) - 1:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup)
                else:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Hata oluştu: {e!s}")

    if not submit_background_task("academic_calendar_fetch", run_fetch):
        bot.send_message(message.chat.id, "⏳ Sistem yoğun, lütfen biraz sonra tekrar deneyin.")
