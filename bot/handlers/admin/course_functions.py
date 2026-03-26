"""
Admin ders yönetimi yardımcı fonksiyonları.
"""

import logging

from telebot import types

from bot.instance import bot_instance as bot
from common.utils import (
    update_user_data,
)

from .data_helpers import load_admin_user_context, load_admin_users
from .helpers import log_admin_action

logger = logging.getLogger("ninova")


def select_user_for_course_management(chat_id):
    """
    Admin'in ders yönetimi için kullanıcı seçmesini sağlar.

    Tüm kullanıcıların listesini butonlar halinde gösterir.
    Her buton kullanıcı adı, ders sayısı ve chat ID içerir.

    :param chat_id: Admin'in chat ID'si
    """
    users = load_admin_users()
    if not users:
        bot.send_message(chat_id, "❌ Kayıtlı kullanıcı yok.")
        return

    markup = types.InlineKeyboardMarkup()
    for uid, data in users.items():
        username = data.get("username", "?")
        url_count = len(data.get("urls", []))
        markup.add(
            types.InlineKeyboardButton(
                f"👤 {username} ({url_count} ders) - {uid}",
                callback_data=f"adm_coursemgmt_{uid}",
            )
        )

    bot.send_message(
        chat_id,
        "👥 Ders yönetmek istediğiniz kullanıcıyı seçin:",
        reply_markup=markup,
    )


def show_user_courses(chat_id, target_user_id):
    """
    Seçilen kullanıcının derslerini ve yönetim seçeneklerini gösterir.

    Kullanıcının takip ettiği tüm derslerin listesini ve
    ders silme/sıfırlama butonlarını gösterir.

    :param chat_id: Admin'in chat ID'si
    :param target_user_id: Hedef kullanıcının chat ID'si
    """
    _users, _user_data, urls, username, user_grades = load_admin_user_context(target_user_id)

    if not urls:
        bot.send_message(
            chat_id,
            f"❌ <b>{username}</b> ({target_user_id}) kullanıcısının takip ettiği ders bulunamadı.",
            parse_mode="HTML",
        )
        return

    response = f"📚 <b>{username} ({target_user_id})</b> - Takip Ettiği Dersler:\n\n"
    for i, url in enumerate(urls, 1):
        course_name = user_grades.get(url, {}).get("course_name", f"Ders {i}")
        response += f"{i}. <b>{course_name}</b>\n<code>{url}</code>\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("❌ Ders Sil", callback_data=f"adm_delcourse_{target_user_id}"),
        types.InlineKeyboardButton(
            "🔄 Tümünü Sıfırla", callback_data=f"adm_clearcourses_{target_user_id}"
        ),
    )
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="adm_manage_courses"))

    if len(response) > 4000:
        response = response[:4000] + "\n... (çok sayıda ders)"

    bot.send_message(chat_id, response, reply_markup=markup, parse_mode="HTML")


def delete_single_course(chat_id, target_user_id):
    """
    Kullanıcıdan tek bir ders seçerek silme menüsünü gösterir.

    Her ders için silme butonu oluşturur. Ders adları ninova_data.json'dan çekilir.

    :param chat_id: Admin'in chat ID'si
    :param target_user_id: Hedef kullanıcının chat ID'si
    """
    _users, _user_data, urls, username, user_grades = load_admin_user_context(target_user_id)

    if not urls:
        bot.send_message(chat_id, "❌ Silinecek ders bulunamadı.")
        return

    markup = types.InlineKeyboardMarkup()
    for i, url in enumerate(urls):
        course_name = user_grades.get(url, {}).get("course_name", "Bilinmeyen Ders")
        display_text = course_name if len(course_name) <= 40 else course_name[:37] + "..."
        markup.add(
            types.InlineKeyboardButton(
                f"❌ {display_text}", callback_data=f"adm_delconf_{target_user_id}_{i}"
            )
        )

    markup.add(
        types.InlineKeyboardButton("🔙 Geri", callback_data=f"adm_coursemgmt_{target_user_id}")
    )

    bot.send_message(
        chat_id,
        f"🗑️ <b>{username}</b> ({target_user_id}) kullanıcısından silmek istediğiniz dersi seçin:",
        reply_markup=markup,
        parse_mode="HTML",
    )


def clear_all_courses(chat_id, target_user_id):
    """
    Kullanıcının tüm derslerini silme onayı menüsünü gösterir.

    Kullanıcıya kaç dersin silineceği gösterilir ve onay ister.

    :param chat_id: Admin'in chat ID'si
    :param target_user_id: Hedef kullanıcının chat ID'si
    """
    _users, user_data, _urls, username, _user_grades = load_admin_user_context(target_user_id)
    url_count = len(user_data.get("urls", []))

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ Evet, Sil", callback_data=f"adm_clearcourses_conf_{target_user_id}"
        ),
        types.InlineKeyboardButton("❌ Vazgeç", callback_data=f"adm_coursemgmt_{target_user_id}"),
    )

    bot.send_message(
        chat_id,
        f"⚠️ <b>{username}</b> ({target_user_id}) kullanıcısının <b>{url_count} dersi</b> silinecektir. Emin misiniz?",
        reply_markup=markup,
        parse_mode="HTML",
    )


def confirm_delete_course(call, target_user_id, course_index, request_id: str | None = None):
    """
    Ders silme onayını işler ve dersi kullanıcının listesinden kaldırır.

    Hem kullanıcıya hem de admin'e bildirim gönderir.

    :param call: CallbackQuery nesnesi
    :param target_user_id: Hedef kullanıcının chat ID'si
    :param course_index: Silinecek dersin indeksi
    :return: Başarılı ise True, değilse False
    """
    _users, _user_data, urls, username, user_grades = load_admin_user_context(target_user_id)

    if course_index >= len(urls):
        bot.answer_callback_query(call.id, "❌ Ders bulunamadı.", show_alert=True)
        return False

    deleted_url = urls[course_index]
    urls.pop(course_index)
    update_user_data(target_user_id, "urls", urls)
    log_admin_action(
        str(call.message.chat.id),
        "manage_courses_delete",
        status="applied",
        request_id=request_id,
        target_id=target_user_id,
        details=f"url={deleted_url}",
    )

    bot.answer_callback_query(call.id, "✅ Ders silindi!")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.debug(f"Could not delete admin confirm-delete prompt: {e}")

    course_name = user_grades.get(deleted_url, {}).get("course_name", deleted_url)

    bot.send_message(
        call.message.chat.id,
        f"✅ <b>Ders Silindi</b>\n\n"
        f"👤 Kullanıcı: <b>{username}</b> ({target_user_id})\n"
        f"🗑️ Silinen Ders: <b>{course_name}</b>\n"
        f"📚 Kalan Dersler: {len(urls)}",
        parse_mode="HTML",
    )

    try:
        bot.send_message(
            target_user_id,
            f"⚠️ <b>Ders Kaldırıldı</b>\n\n"
            f"Admin tarafından aşağıdaki ders takip listesinden kaldırıldı:\n\n"
            f"<b>{course_name}</b>\n\n"
            f"📚 Kalan Dersler: {len(urls)}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug(f"Could not notify user {target_user_id} after course deletion: {e}")

    return True


def confirm_clear_all_courses(call, target_user_id, request_id: str | None = None):
    """
    Tüm dersleri silme onayını işler.

    Kullanıcının tüm ders listesini temizler.
    Hem kullanıcıya hem de admin'e bildirim gönderir.

    :param call: CallbackQuery nesnesi
    :param target_user_id: Hedef kullanıcının chat ID'si
    """
    _users, user_data, _urls, username, _user_grades = load_admin_user_context(target_user_id)
    url_count = len(user_data.get("urls", []))

    update_user_data(target_user_id, "urls", [])
    log_admin_action(
        str(call.message.chat.id),
        "manage_courses_clear",
        status="applied",
        request_id=request_id,
        target_id=target_user_id,
        details=f"removed={url_count}",
    )

    bot.answer_callback_query(call.id, f"✅ {url_count} ders silindi!")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.debug(f"Could not delete admin clear-all confirmation message: {e}")

    bot.send_message(
        call.message.chat.id,
        f"✅ <b>Tüm Dersler Silindi</b>\n\n"
        f"👤 Kullanıcı: <b>{username}</b> ({target_user_id})\n"
        f"🗑️ Silinen Dersler: {url_count}",
        parse_mode="HTML",
    )

    try:
        bot.send_message(
            target_user_id,
            f"⚠️ <b>Tüm Dersler Kaldırıldı</b>\n\n"
            f"Admin tarafından takip ettiğiniz <b>{url_count} ders</b> kaldırıldı.\n\n"
            f"/otoders komutu ile yeni dersleri ekleyebilirsiniz.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug(f"Could not notify user {target_user_id} after clear-all: {e}")
