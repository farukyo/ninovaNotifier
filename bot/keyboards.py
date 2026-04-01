from telebot import types


def build_main_keyboard():
    """
    Kullanıcının ana etkileşim menüsü için klavye oluşturur.

    :return: ReplyKeyboardMarkup nesnesi
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Notlar", "📅 Ödevler", "📖 Dersler")
    kb.row("📆 Akademik Takvim", "✨ Ekstra")
    kb.row("🐝 Arı24", "📞 İTÜ Rehber")
    kb.row("👤 Kullanıcı", "🔍 Duyurularda Ara")

    return kb


def build_user_menu_keyboard(is_admin: bool = False):
    """
    Kullanıcı ayarları alt menüsü için klavye oluşturur.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔐 Giriş Yap")
    if is_admin:
        kb.row("👑 Admin", "🚪 Ayrıl")
    else:
        kb.row("🚪 Ayrıl")
    kb.row("🔙 Geri")
    return kb


def build_extra_features_keyboard():
    """
    Ek özellikler alt menüsü için klavye oluşturur.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔄 Kontrol", "📋 Durum")
    kb.row("❓ Yardım", "🍽 Yemekhane")
    kb.row("🔙 Geri")
    return kb


def build_ari24_menu_keyboard(daily_sub_status=False):
    """
    Arı24 alt menüsü için klavye oluşturur.
    Status'a göre buton metni değişir.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🌍 Keşfet", "📰 Haberler")
    kb.row("🔔 Abone Ol", "❤️ Kulüplerim")

    status_icon = "✅" if daily_sub_status else "❌"
    kb.row(f"☀️ Günlük Bülten: {status_icon}", "🔙 Geri")
    return kb


def build_cancel_keyboard():
    """Return a simple ReplyKeyboardMarkup with a cancel button.

    Use a clear visual label so users can tap instead of typing.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("⛔ İptal")
    return kb


def build_rehber_ad_keyboard():
    """İTÜ Rehber araması için İsim giriş menüsü oluşturur."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("Bilinmiyor", "⛔ İptal")
    return kb


def build_rehber_soyad_keyboard():
    """İTÜ Rehber araması için Soyisim giriş menüsü oluşturur."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("Bilinmiyor", "⛔ İptal")
    return kb
