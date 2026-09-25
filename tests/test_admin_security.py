"""Tests for admin authorization and admin course deletion safety."""

from types import SimpleNamespace

import pytest

from bot.handlers.admin import course_functions, helpers
from core import storage

ADMIN_ID = 1001


@pytest.fixture(autouse=True)
def admin_ids(monkeypatch):
    monkeypatch.setattr(helpers, "ADMIN_TELEGRAM_IDS", [ADMIN_ID])


def _message(user_id, chat_id, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id), chat=SimpleNamespace(id=chat_id, type=chat_type)
    )


def _call(user_id, chat_id, chat_type="private"):
    return SimpleNamespace(
        id="cb",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=chat_type), message_id=1),
    )


def test_is_admin_accepts_admin_in_private_chat():
    assert helpers.is_admin(_message(ADMIN_ID, ADMIN_ID))
    assert helpers.is_admin(_call(ADMIN_ID, ADMIN_ID))


def test_is_admin_rejects_non_admin_even_in_admin_group():
    # Regresyon: chat.id kontrol edildiğinde, admin ID'si bir grup olursa grubun
    # tüm üyeleri admin sayılıyordu.
    assert not helpers.is_admin(_message(5, ADMIN_ID, "group"))
    assert not helpers.is_admin(_call(5, ADMIN_ID, "group"))


def test_is_admin_rejects_admin_outside_private_chat():
    assert not helpers.is_admin(_message(ADMIN_ID, -500, "supergroup"))


def test_is_admin_rejects_inline_callback_without_message():
    call = SimpleNamespace(from_user=SimpleNamespace(id=ADMIN_ID), message=None)
    assert not helpers.is_admin(call)


class _FakeBot:
    def __init__(self):
        self.answers = []

    def answer_callback_query(self, _call_id, text=None, **_kw):
        self.answers.append(text)

    def delete_message(self, *_a, **_kw):
        pass

    def send_message(self, *_a, **_kw):
        pass


@pytest.fixture
def admin_env(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(storage, "DATA_FILE", str(tmp_path / "ninova_data.json"))
    fake_bot = _FakeBot()
    monkeypatch.setattr(course_functions, "bot", fake_bot)
    storage.save_all_users({"7": {"username": "u", "urls": ["a", "b", "c"]}})
    return fake_bot


@pytest.mark.usefixtures("admin_env")
def test_confirm_delete_course_rejects_negative_index():
    # Regresyon: sadece üst sınır kontrol ediliyordu; sahte "-1" son dersi siliyordu.
    assert course_functions.confirm_delete_course(_call(ADMIN_ID, ADMIN_ID), "7", -1) is False
    assert storage.load_all_users()["7"]["urls"] == ["a", "b", "c"]


@pytest.mark.usefixtures("admin_env")
def test_confirm_delete_course_removes_only_target():
    assert course_functions.confirm_delete_course(_call(ADMIN_ID, ADMIN_ID), "7", 1) is True
    assert storage.load_all_users()["7"]["urls"] == ["a", "c"]


@pytest.mark.usefixtures("admin_env")
def test_clear_all_courses_does_not_create_ghost_user():
    course_functions.confirm_clear_all_courses(_call(ADMIN_ID, ADMIN_ID), "404")
    assert "404" not in storage.load_all_users()
