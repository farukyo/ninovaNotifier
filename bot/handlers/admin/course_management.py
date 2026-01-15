"""
Admin ders yönetimi callback'leri.
"""

import contextlib

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

    target_user_id = call.data.split("_", 2)[-1]
    bot.answer_callback_query(call.id)

    with contextlib.suppress(Exception):
        bot.delete_message(call.message.chat.id, call.message.message_id)

    show_user_courses(str(call.message.chat.id), target_user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_delcourse_"))
def handle_delete_course_select(call):
    """
    Silinecek ders seçim menüsünü gösterir.

    :param call: CallbackQuery nesnesi (adm_delcourse_<chat_id> formatında)
    """
    if not is_admin(call):
        return

    target_user_id = call.data.split("_", 2)[-1]
    bot.answer_callback_query(call.id)

    with contextlib.suppress(Exception):
        bot.delete_message(call.message.chat.id, call.message.message_id)

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

    parts = call.data.split("_")
    course_index = int(parts[-1])
    target_user_id = "_".join(parts[2:-1])

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

    target_user_id = call.data.split("_", 2)[-1]
    bot.answer_callback_query(call.id)

    with contextlib.suppress(Exception):
        bot.delete_message(call.message.chat.id, call.message.message_id)

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

    target_user_id = call.data.split("_", 3)[-1]
    confirm_clear_all_courses(call, target_user_id)
    select_user_for_course_management(str(call.message.chat.id))
