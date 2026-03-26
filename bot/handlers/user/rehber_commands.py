import requests
from telebot import types

from bot.instance import bot_instance as bot
from bot.keyboards import build_main_keyboard, build_rehber_ad_keyboard, build_rehber_soyad_keyboard
from bot.utils import is_cancel_text
from common.config import USER_SESSIONS, load_all_users
from common.utils import decrypt_password, escape_html
from services.rehber.scraper import RehberScraper

# Geçici hafıza: hangi chat_id hangi arama sonuçlarını (veya query'sini) tutuyor.
REHBER_TEMP_DATA = {}


@bot.message_handler(func=lambda message: message.text == "📞 İTÜ Rehber")
def handle_rehber_start(message):
    chat_id = str(message.chat.id)
    REHBER_TEMP_DATA[chat_id] = {"ad": "", "soyad": "", "results": []}

    prompt = bot.send_message(
        chat_id=message.chat.id,
        text="📞 <b>İTÜ Rehber Araması</b>\n\nLütfen aranacak kişinin <b>Adını</b> girin:\n(Sadece soyad biliyorsanız 'Bilinmiyor' seçebilirsiniz)",
        parse_mode="HTML",
        reply_markup=build_rehber_ad_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_rehber_ad)


def process_rehber_ad(message):
    if is_cancel_text(message.text):
        REHBER_TEMP_DATA.pop(str(message.chat.id), None)
        bot.send_message(
            message.chat.id,
            "❌ İTÜ Rehber araması iptal edildi.",
            reply_markup=build_main_keyboard(),
        )
        return

    chat_id = str(message.chat.id)
    ad = message.text.strip()

    if ad == "Bilinmiyor":
        ad = "   "  # 3 boşluk gönderilecek

    if chat_id not in REHBER_TEMP_DATA:
        REHBER_TEMP_DATA[chat_id] = {}

    REHBER_TEMP_DATA[chat_id]["ad"] = ad

    prompt = bot.send_message(
        chat_id=message.chat.id,
        text="Lütfen aranacak kişinin <b>Soyadını</b> girin:\n(Sadece ad biliyorsanız 'Bilinmiyor' seçebilirsiniz)",
        parse_mode="HTML",
        reply_markup=build_rehber_soyad_keyboard(),
    )
    bot.register_next_step_handler(prompt, process_rehber_soyad)


def process_rehber_soyad(message):
    if is_cancel_text(message.text):
        REHBER_TEMP_DATA.pop(str(message.chat.id), None)
        bot.send_message(
            message.chat.id,
            "❌ İTÜ Rehber araması iptal edildi.",
            reply_markup=build_main_keyboard(),
        )
        return

    chat_id = str(message.chat.id)
    soyad = message.text.strip()

    if soyad == "Bilinmiyor":
        soyad = "  "  # 2 boşluk gönderilecek

    if chat_id not in REHBER_TEMP_DATA:
        REHBER_TEMP_DATA[chat_id] = {"ad": "   "}

    REHBER_TEMP_DATA[chat_id]["soyad"] = soyad
    ad = REHBER_TEMP_DATA[chat_id]["ad"]

    if not ad.strip() and not soyad.strip():
        bot.send_message(
            message.chat.id,
            "❌ <b>Hata:</b> Ad ve Soyad aynı anda 'Bilinmiyor' seçilemez! Lütfen menüden aramayı tekrar başlatın.",
            parse_mode="HTML",
            reply_markup=build_main_keyboard(),
        )
        return

    bot.send_message(
        message.chat.id,
        f"🔎 <b>'{ad.strip()} {soyad.strip()}'</b> İTÜ Rehberde aranıyor...\nLütfen bekleyiniz.",
        parse_mode="HTML",
        reply_markup=build_main_keyboard(),
    )

    # Session setup ve SSO login
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = requests.Session()

    session = USER_SESSIONS[chat_id]
    scraper = RehberScraper(session)

    # Kullanıcı bilgilerini al ve Rehber SSO'ya giriş yap
    users = load_all_users()
    user_info = users.get(chat_id, {})
    username = user_info.get("username", "")
    encrypted_pw = user_info.get("password", "")
    password = decrypt_password(encrypted_pw) if encrypted_pw else ""

    if username and password and not scraper.is_logged_in():
        login_ok = scraper.login_to_rehber(username, password)
        if not login_ok:
            bot.send_message(
                message.chat.id,
                "⚠️ Rehber'e giriş yapılamadı. Sonuçlar sınırlı olabilir (e-posta/telefon görünmeyebilir).",
            )

    results = scraper.search_person(ad, soyad)
    REHBER_TEMP_DATA[chat_id]["results"] = results

    if not results:
        bot.send_message(
            message.chat.id,
            "❌ Eşleşen kişi bulunamadı. Lütfen bilgileri kontrol edip tekrar deneyin.",
        )
        return

    # Bölüm / Fakülte gruplaması (Filtreleme)
    departments = {}
    for i, r in enumerate(results):
        d = r.get("department", "Bilinmeyen Bölüm")
        if d not in departments:
            departments[d] = []
        departments[d].append(i)

    msg_text = f"✅ Toplam {len(results)} kişi bulundu.\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    if len(departments) > 1:
        msg_text += "<b>Lütfen filtrelemek için bir bölüm/fakülte seçin:</b>"
        for idx, (dept, items) in enumerate(departments.items()):
            btn_text = f"🏢 {dept} ({len(items)})"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"rehdept_{idx}"))
        markup.add(types.InlineKeyboardButton("📋 Tümünü Göster", callback_data="rehdept_all"))

        bot.send_message(message.chat.id, msg_text, parse_mode="HTML", reply_markup=markup)
    else:
        # Sadece 1 departman varsa veya çok az kişi varsa direkt sonuçları bas.
        msg_text = format_rehber_results(results, list(range(len(results))))
        bot.send_message(message.chat.id, msg_text, parse_mode="HTML")


def format_rehber_results(results, indices):
    text = ""
    for i in indices:
        r = results[i]
        title = r.get("title", "")
        name = r.get("name", "")
        display_name = f"{title} {name}".strip() if title else name

        text += f"👤 <b>{escape_html(display_name)}</b>\n"

        unit = r.get("unit", "")
        if unit:
            text += f"🏛 <i>{escape_html(unit)}</i>\n"

        dept = r.get("department", "")
        if dept:
            text += f"🏢 {escape_html(dept)}\n"

        if r.get("email"):
            text += f"📧 <code>{escape_html(r['email'])}</code>\n"
        if r.get("phone"):
            text += f"📞 <code>{escape_html(r['phone'])}</code>\n"

        for key, val in r.get("extras", {}).items():
            text += f"📌 <b>{escape_html(key)}:</b> <code>{escape_html(val)}</code>\n"

        text += "-------------------\n"
    return text


@bot.callback_query_handler(func=lambda call: call.data.startswith("rehdept_"))
def handle_rehber_department_filter(call):
    chat_id = str(call.message.chat.id)
    action = call.data.split("_")[1]

    data = REHBER_TEMP_DATA.get(chat_id, {})
    results = data.get("results", [])

    if not results:
        bot.answer_callback_query(call.id, "Süresi dolmuş arama veya geçersiz.")
        return

    departments = {}
    dept_keys = []

    for i, r in enumerate(results):
        d = r.get("department", "Bilinmeyen Bölüm")
        if d not in departments:
            departments[d] = []
            dept_keys.append(d)
        departments[d].append(i)

    if action == "all":
        indices = list(range(len(results)))
        msg = f"📋 <b>Tüm Sonuçlar ({len(results)} kişi)</b>\n\n"
    else:
        idx = int(action)
        if idx >= len(dept_keys):
            return
        dept = dept_keys[idx]
        indices = departments[dept]
        msg = f"🏢 <b>{escape_html(dept)} ({len(indices)} kişi)</b>\n\n"

    msg += format_rehber_results(results, indices)

    if len(msg) > 4000:
        msg = msg[:3950] + "\n\n⚠️ Sonuçlar çok uzun olduğu için kesildi."

    bot.edit_message_text(
        chat_id=chat_id, message_id=call.message.message_id, text=msg, parse_mode="HTML"
    )
