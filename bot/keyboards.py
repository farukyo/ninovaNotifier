from telebot import types


def build_main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("/notlar", "/odevler")
    kb.row("/dersler", "/otoders", "/ekle")
    kb.row("/sil", "/liste", "/kontrol")
    kb.row("/durum", "/search", "/help")
    kb.row("/ayril")
    return kb
