"""Tests for core/storage.py — atomic per-user updates and password encryption."""

import json

import pytest

from core import storage
from core.utils import decrypt_password


@pytest.fixture(autouse=True)
def data_files(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    data_file = tmp_path / "ninova_data.json"
    monkeypatch.setattr(storage, "USERS_FILE", str(users_file))
    monkeypatch.setattr(storage, "DATA_FILE", str(data_file))
    return users_file, data_file


def test_update_user_data_encrypts_password(data_files):
    # Regresyon: storage, core.crypto.encrypt_password'ı eksik argümanla çağırıyordu
    # (TypeError) ve yeni kullanıcıların şifresi hiç kaydedilmiyordu.
    users_file, _ = data_files
    storage.update_user_data("42", "password", "s3cret")

    saved = json.loads(users_file.read_text(encoding="utf-8"))["42"]["password"]
    assert saved != "s3cret"
    assert decrypt_password(saved) == "s3cret"


def test_update_user_data_refuses_to_overwrite_corrupt_file(data_files):
    users_file, _ = data_files
    users_file.write_text("{bozuk", encoding="utf-8")

    with pytest.raises(RuntimeError):
        storage.update_user_data("42", "username", "x")
    assert users_file.read_text(encoding="utf-8") == "{bozuk"


def test_modify_user_is_atomic_and_keeps_other_fields():
    storage.save_all_users({"1": {"urls": ["a"], "temp_expired_courses": ["b"]}})

    def _add(data):
        data["urls"] = data["urls"] + data.pop("temp_expired_courses")

    result = storage.modify_user("1", _add)

    assert result == {"urls": ["a", "b"]}
    assert storage.load_all_users() == {"1": {"urls": ["a", "b"]}}
    assert storage.modify_user("missing", _add) is None


def test_update_user_grades_does_not_clobber_other_users():
    storage.save_all_users({"1": {"urls": ["u1", "u3"]}, "2": {"urls": ["u2"]}})
    storage.save_grades({"1": {"u1": {"course_name": "A"}}, "2": {"u2": {"course_name": "B"}}})

    storage.update_user_grades("1", {"u3": {"course_name": "C"}})

    grades = storage.load_saved_grades()
    assert grades["2"] == {"u2": {"course_name": "B"}}
    assert list(grades["1"]) == ["u1", "u3"]


def test_delete_helpers():
    storage.save_all_users({"1": {}, "2": {}})
    storage.save_grades({"1": {"u1": {}}, "2": {"u2": {}, "u3": {}}})

    assert storage.delete_user("1") is True
    assert storage.delete_user("1") is False
    assert storage.delete_user_grades("1") is True
    assert storage.delete_course_data("2", "u2") is True
    assert storage.delete_course_data("2", "nope") is False

    assert storage.load_all_users() == {"2": {}}
    assert storage.load_saved_grades() == {"2": {"u3": {}}}


def test_update_user_grades_skips_untracked_courses_and_missing_users():
    storage.save_all_users({"1": {"urls": ["u1"]}})

    assert storage.update_user_grades("1", {"u1": {"n": 1}, "gone": {"n": 2}}) == 1
    assert storage.update_user_grades("404", {"u1": {"n": 1}}) == 0
    assert storage.load_saved_grades() == {"1": {"u1": {"n": 1}}}


def test_add_user_urls_keeps_courses_deleted_during_scan_deleted():
    # Regresyon: oto ders / forceoto / manuel ekleme, taramadan önce alınan listeyi
    # update_user_data ile yazıyordu; tarama sırasında silinen ders geri geliyor ve
    # list(set(...)) ders sırasını (menü indekslerini) karıştırıyordu.
    storage.save_all_users({"1": {"urls": ["a", "b", "c"], "username": "x"}})

    # Tarama sürerken kullanıcı "b"yi siliyor.
    storage.modify_user("1", lambda d: d.__setitem__("urls", ["a", "c"]))

    # Tarama sonunda sadece yeni bulunan dersler eklenir.
    assert storage.add_user_urls("1", ["d", "e"]) == ["d", "e"]

    user = storage.load_all_users()["1"]
    assert user["urls"] == ["a", "c", "d", "e"]
    assert user["username"] == "x"


def test_add_user_urls_only_adds_new_and_skips_missing_user():
    storage.save_all_users({"1": {"urls": ["a", "c"]}})

    assert storage.add_user_urls("1", ["c", "d", "e", "d"]) == ["d", "e"]
    assert storage.load_all_users()["1"]["urls"] == ["a", "c", "d", "e"]
    assert storage.add_user_urls("1", ["a"]) == []

    # Silinmiş kullanıcı için hayalet kayıt oluşturulmaz.
    assert storage.add_user_urls("404", ["x"]) is None
    assert "404" not in storage.load_all_users()


def test_prune_untracked_course_data_uses_current_url_list():
    storage.save_all_users({"1": {"urls": ["u1", "u2"]}, "2": {"urls": []}})
    storage.save_grades({"1": {"u1": {}, "u2": {}, "old": {}}, "2": {"x": {}}, "3": {"y": {}}})

    assert storage.prune_untracked_course_data("1") == 1
    assert storage.prune_untracked_course_data("2") == 1
    assert storage.prune_untracked_course_data("3") == 0  # kullanıcı kaydı yok, dokunma
    assert storage.prune_untracked_course_data("1") == 0

    assert storage.load_saved_grades() == {"1": {"u1": {}, "u2": {}}, "3": {"y": {}}}
