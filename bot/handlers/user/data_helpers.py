"""Shared data access helpers for user handlers."""

from __future__ import annotations

from common.config import load_all_users
from common.utils import load_saved_grades


def load_user_snapshot(chat_id: str, *, urls_source: str = "user_data") -> tuple[dict, dict, list]:
    """Load user_data, user_grades and URL list in a single helper.

    Args:
        chat_id: User chat id as string.
        urls_source: "user_data" uses users.json URLs, "grades" uses ninova_data keys.
    """
    users = load_all_users()
    user_data = users.get(chat_id, {})

    all_grades = load_saved_grades()
    user_grades = all_grades.get(chat_id, {})

    urls = list(user_grades.keys()) if urls_source == "grades" else user_data.get("urls", [])

    return user_data, user_grades, urls


def load_user_grades(chat_id: str) -> dict:
    """Load only grade payload for a user."""
    return load_saved_grades().get(chat_id, {})


def load_user_profile(chat_id: str) -> dict:
    """Load only user profile payload for a user."""
    return load_all_users().get(chat_id, {})
