from telebot import types


def get_back_button(callback_data: str, text: str = "↩️ Geri"):
    """Standart bir geri butonu döndürür."""
    return types.InlineKeyboardButton(text, callback_data=callback_data)


def get_main_menu_button(text: str = "↩️ Ana Menü"):
    """Ana menüye dönüş butonu döndürür."""
    return types.InlineKeyboardButton(text, callback_data="main_menu")


def get_global_kontrol_button(text: str = "🔄 Tümünü Kontrol Et"):
    """Tümünü kontrol et butonu döndürür."""
    return types.InlineKeyboardButton(text, callback_data="global_kontrol")


def build_back_keyboard(callback_data: str):
    """Sadece 'Geri' butonu içeren basit bir klavye oluşturur."""
    markup = types.InlineKeyboardMarkup()
    markup.add(get_back_button(callback_data))
    return markup


def build_course_detail_keyboard(course_idx: int):
    """Ders detay sayfası (Not, Ödev, Dosya, Duyuru) klavyesini oluşturur."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Notlar", callback_data=f"det_{course_idx}_not"),
        types.InlineKeyboardButton("📅 Ödevler", callback_data=f"det_{course_idx}_odev"),
        types.InlineKeyboardButton("📁 Dosyalar", callback_data=f"det_{course_idx}_dosya"),
        types.InlineKeyboardButton("📣 Duyurular", callback_data=f"det_{course_idx}_duyuru"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data=f"kontrol_{course_idx}"))
    markup.add(get_main_menu_button())
    return markup


def build_confirm_keyboard(
    yes_data: str, no_data: str, yes_text: str = "Evet", no_text: str = "Hayır"
):
    """Evet/Hayır onay ekranı klavyesi oluşturur."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(yes_text, callback_data=yes_data),
        types.InlineKeyboardButton(no_text, callback_data=no_data),
    )
    return markup


def build_manual_manage_courses_keyboard(urls, user_grades):
    """Manuel ders yönetimi (Silme) sayfasındaki ders listesi klavyesini oluşturur."""
    markup = types.InlineKeyboardMarkup()
    for i, url in enumerate(urls):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i + 1}")
        display_text = course_name if len(course_name) <= 40 else course_name[:37] + "..."
        markup.add(types.InlineKeyboardButton(f"🗑️ {display_text}", callback_data=f"del_req_{i}"))
    markup.add(get_back_button("manual_back"))
    return markup


def build_main_dashboard_keyboard(user_grades):
    """Kullanıcının takip ettiği dersleri listeleyen ana menü klavyesi."""
    markup = types.InlineKeyboardMarkup()
    for i, (_url, data) in enumerate(user_grades.items()):
        markup.add(
            types.InlineKeyboardButton(
                f"📚 {data.get('course_name', 'Bilinmeyen Ders')}",
                callback_data=f"crs_{i}",
            )
        )
    markup.add(get_global_kontrol_button())
    markup.add(
        types.InlineKeyboardButton("📝 Manuel Ders Yönetimi", callback_data="manual_menu_open")
    )
    return markup


def build_manual_menu():
    """Return an InlineKeyboardMarkup for the manual course menu."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Ders Ekle", callback_data="manual_add"),
        types.InlineKeyboardButton("🗑️ Ders Sil", callback_data="manual_delete"),
        types.InlineKeyboardButton("📋 Ders Listesi", callback_data="manual_list"),
    )
    return markup
