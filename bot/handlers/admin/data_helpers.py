"""
Admin handler'lari icin ortak veri erisim helper'lari.
"""

from common.config import load_all_users
from common.utils import load_saved_grades


def load_admin_users():
    """
    Tum kullanicilari users.json'dan yukler.
    """
    return load_all_users()


def load_admin_grades():
    """
    Tum not verisini ninova_data.json'dan yukler.
    """
    return load_saved_grades()


def load_admin_user_context(target_user_id):
    """
    Hedef kullaniciya ait users.json ve ninova_data.json baglamini tek noktadan dondurur.
    """
    users = load_admin_users()
    user_data = users.get(target_user_id, {})
    urls = user_data.get("urls", [])
    username = user_data.get("username", "?")

    all_grades = load_admin_grades()
    user_grades = all_grades.get(target_user_id, {})

    return users, user_data, urls, username, user_grades
