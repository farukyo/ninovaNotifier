"""
Admin ders yönetimi callback'leri.
"""

import logging

from bot.callback_parsing import callback_parse_fail, parse_int_part, split_callback_data
from bot.instance import bot_instance as bot

from .course_functions import (
    clear_all_courses,
    confirm_clear_all_courses,
    confirm_delete_course,
    delete_single_course,
    select_user_for_course_management,
    show_user_courses,
)
from .helpers import is_admin

logger = logging.getLogger("ninova")


@bot.callback_query_handler(func=lambda call: call.data == "adm_manage_courses")
def handle_course_management(call):
    """
    Ders yönetimi ana menüsünü açar.

    :param call: CallbackQuery nesnesi
    """
    if not is_admin(call):
        return

    bot.answer_callback_query(call.id)
    select_user_for_course_management(str(call.message.chat.id))


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_coursemgmt_"))
def handle_user_course_select(call):
    """
    Kullanıcı seçimi sonrası dersler menüsünü gösterir.

    :param call: CallbackQuery nesnesi (adm_coursemgmt_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data, maxsplit=2)
    target_user_id = parts[2] if len(parts) > 2 else ""
    if not target_user_id:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Gecersiz kullanici secimi."
        )
        return
    bot.answer_callback_query(call.id)

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.debug(f"Could not delete admin course management menu message: {e}")

    show_user_courses(str(call.message.chat.id), target_user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_delcourse_"))
def handle_delete_course_select(call):
    """
    Silinecek ders seçim menüsünü gösterir.

    :param call: CallbackQuery nesnesi (adm_delcourse_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data, maxsplit=2)
    target_user_id = parts[2] if len(parts) > 2 else ""
    if not target_user_id:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Gecersiz kullanici secimi."
        )
        return
    bot.answer_callback_query(call.id)

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.debug(f"Could not delete admin delete-course menu message: {e}")

    delete_single_course(str(call.message.chat.id), target_user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_delconf_"))
def handle_delete_course_confirm(call):
    """
    Ders silme onayını işler ve dersi kullanıcının listesinden kaldırır.

    Hem kullanıcıya hem de admin'e bildirim gönderir.

    :param call: CallbackQuery nesnesi (adm_delconf_<chat_id>_<course_index> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data)
    course_index = parse_int_part(parts, len(parts) - 1)
    target_user_id = "_".join(parts[2:-1]) if len(parts) > 3 else ""
    if course_index is None or not target_user_id:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Gecersiz ders silme istegi."
        )
        return

    if confirm_delete_course(call, target_user_id, course_index):
        show_user_courses(str(call.message.chat.id), target_user_id)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("adm_clearcourses_")
    and not call.data.startswith("adm_clearcourses_conf_")
)
def handle_clear_courses(call):
    """
    Tüm dersleri silme onayı ekranını gösterir.

    :param call: CallbackQuery nesnesi (adm_clearcourses_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data, maxsplit=2)
    target_user_id = parts[2] if len(parts) > 2 else ""
    if not target_user_id:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Gecersiz kullanici secimi."
        )
        return
    bot.answer_callback_query(call.id)

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.debug(f"Could not delete admin clear-courses menu message: {e}")

    clear_all_courses(str(call.message.chat.id), target_user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_clearcourses_conf_"))
def handle_clear_courses_confirm(call):
    """
    Tüm dersleri silme onayını işler.

    Kullanıcının tüm ders listesini temizler.
    Hem kullanıcıya hem de admin'e bildirim gönderir.

    :param call: CallbackQuery nesnesi (adm_clearcourses_conf_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    parts = split_callback_data(call.data, maxsplit=3)
    target_user_id = parts[3] if len(parts) > 3 else ""
    if not target_user_id:
        callback_parse_fail(
            lambda msg: bot.answer_callback_query(call.id, msg), "Gecersiz toplu silme istegi."
        )
        return
    confirm_clear_all_courses(call, target_user_id)
    select_user_for_course_management(str(call.message.chat.id))
