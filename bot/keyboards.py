from telebot import types


def build_main_keyboard():
    """
    Kullanıcının ana etkileşim menüsü için klavye oluşturur.

    :param user_id: İsteyen kullanıcının ID'si (Admin kontrolü için)
    :return: ReplyKeyboardMarkup nesnesi
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Notlar", "📅 Ödevler", "📖 Dersler")
    kb.row("🤖 Oto Ders", "🔄 Kontrol", "📆 Akademik Takvim")
    kb.row("🐝 Arı24", "🔍 Ara", "🍽 Yemekhane")
    kb.row("📋 Durum", "❓ Yardım", "👤 Kullanıcı")

    return kb


def build_user_menu_keyboard():
    """
    Kullanıcı ayarları alt menüsü için klavye oluşturur.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("👤 Kullanıcı Adı", "🔐 Şifre")
    kb.row("👑 Admin", "🚪 Ayrıl")
    kb.row("🔙 Geri")
    return kb


def build_extra_features_keyboard():
    """
    Ek özellikler alt menüsü için klavye oluşturur.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🐝 Arı24")
    # Gelecekte buraya yeni özellikler eklenecek
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
