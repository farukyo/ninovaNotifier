import os

from telebot import types


def build_main_keyboard(user_id=None):
    """
    Kullanıcının ana etkileşim menüsü için klavye oluşturur.

    :param user_id: İsteyen kullanıcının ID'si (Admin kontrolü için)
    :return: ReplyKeyboardMarkup nesnesi
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Notlar", "📅 Ödevler", "📖 Dersler")
    kb.row("🤖 Oto Ders", "🔄 Kontrol", "📆 Akademik Takvim")
    kb.row("🔍 Ara", "📋 Durum", "❓ Yardım")
    kb.row("👤 Kullanıcı Adı", "🔐 Şifre")

    # Sadece admin ise Admin butonunu ekle
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if user_id and str(user_id) == str(admin_id):
        kb.row("👑 Admin", "🚪 Ayrıl")
    else:
        kb.row("🚪 Ayrıl")

    return kb


def build_manual_menu():
    """Return an InlineKeyboardMarkup for the manual course menu."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Ders Ekle", callback_data="manual_add"),
        types.InlineKeyboardButton("🗑️ Ders Sil", callback_data="manual_delete"),
        types.InlineKeyboardButton("📋 Ders Listesi", callback_data="manual_list"),
    )
    return kb


def build_cancel_keyboard():
    """Return a simple ReplyKeyboardMarkup with a cancel button.

    Use a clear visual label so users can tap instead of typing.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("⛔ İptal")
    return kb
