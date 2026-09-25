"""Tests for the change-detection / notification flow in main.py."""

import pytest

import main
from bot.callback_parsing import url_token
from core import storage


def _course(**overrides):
    data = {
        "course_name": "BLG 101E - Intro",
        "grades": {"Vize": {"not": "80", "agirlik": "", "detaylar": {}}},
        "assignments": [
            {
                "id": "1",
                "name": "HW1",
                "url": "https://ninova.itu.edu.tr/Sinif/1/Odev/1",
                "start_date": "01 Ocak 2025 00:00",
                "end_date": "10 Ocak 2025 23:59",
                "is_submitted": False,
                "description": "desc",
                "source_files": [{"name": "hw1.pdf", "size": "1 MB", "url": "https://s/1"}],
                "required_files": [],
            }
        ],
        "files": [{"name": "a.pdf", "url": "https://f/1", "date": "d1", "size": "1 MB"}],
        "announcements": [
            {
                "id": "9",
                "title": "T",
                "url": "https://a/9",
                "author": "X",
                "date": "d",
                "content": "c",
            }
        ],
        "fetch_success": True,
        "failed_sections": [],
    }
    data.update(overrides)
    return data


def _saved(course):
    return {k: v for k, v in course.items() if k not in ("fetch_success", "failed_sections")}


def test_failed_sections_keep_saved_data_without_notifications():
    saved = _saved(_course())
    current = _course(
        assignments=[],
        files=[],
        announcements=[],
        fetch_success=False,
        failed_sections=["assignments", "files", "announcements"],
    )

    sections, changes, new_files, updated_files, asf = main._compare_course_data(
        current, saved, None, "BLG 101E"
    )

    assert (sections, changes, new_files, updated_files, asf) == ([], [], [], [], [])
    # Kayda yazılacak veri eski veriyle aynı kalmalı (boş listeyle ezilmemeli).
    assert current["assignments"] == saved["assignments"]
    assert current["files"] == saved["files"]
    assert current["announcements"] == saved["announcements"]


def test_missing_assignment_detail_does_not_report_deleted_source_files():
    saved = _saved(_course())
    saved["assignments"][0]["reminders_sent"] = ["24h"]
    listed_only = {
        k: v
        for k, v in saved["assignments"][0].items()
        if k not in ("description", "source_files", "required_files", "reminders_sent")
    }
    current = _course(assignments=[listed_only])

    _sections, changes, *_ = main._compare_course_data(current, saved, None, "BLG 101E")

    assert changes == []
    assert current["assignments"][0]["source_files"] == saved["assignments"][0]["source_files"]
    assert current["assignments"][0]["reminders_sent"] == ["24h"]


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setattr(storage, "DATA_FILE", str(tmp_path / "ninova_data.json"))
    monkeypatch.setattr(main.time, "sleep", lambda _s: None)
    storage.save_all_users(
        {"1": {"username": "user", "urls": ["https://ninova.itu.edu.tr/Sinif/1"]}}
    )

    sent_messages, sent_buttons = [], []
    monkeypatch.setattr(main, "send_telegram_message", lambda _cid, msg: sent_messages.append(msg))

    class _FakeBot:
        def send_message(self, _chat_id, _text, reply_markup=None, **_kwargs):
            sent_buttons.append(reply_markup.keyboard[0][0].callback_data)

    monkeypatch.setattr(main, "bot", _FakeBot())
    return sent_messages, sent_buttons


def test_process_user_results_saves_and_notifies(isolated_storage):
    # Regresyon: otomatik kontrol _compare_course_data'nın 5'li dönüşünü 3 değişkene
    # açıyordu (ValueError) ve ana döngü çöküp botu kapatıyordu.
    sent_messages, sent_buttons = isolated_storage
    storage.save_grades({"other": {"x": {"course_name": "keep me"}}})
    url = "https://ninova.itu.edu.tr/Sinif/1"

    changes = main._process_user_results(
        "1",
        "user",
        None,
        {url: _course(announcements=[])},
        silent=False,
        include_reminders=False,
    )

    assert "YENİ NOT: Vize -> 80" in changes
    assert "YENİ DOSYA: a.pdf" in changes
    assert len(sent_messages) == 1
    assert f"dl_0_0_{url_token('https://f/1')}" in sent_buttons
    assert f"asf_0_0_0_{url_token('https://s/1')}" in sent_buttons

    grades = storage.load_saved_grades()
    assert grades["other"] == {"x": {"course_name": "keep me"}}
    assert grades["1"][url]["files"][0]["name"] == "a.pdf"


def test_process_user_results_silent_sends_nothing(isolated_storage):
    sent_messages, sent_buttons = isolated_storage
    url = "https://ninova.itu.edu.tr/Sinif/1"

    changes = main._process_user_results(
        "1", "user", None, {url: _course(announcements=[])}, silent=True, include_reminders=False
    )

    assert changes
    assert sent_messages == []
    assert sent_buttons == []
    assert url in storage.load_saved_grades()["1"]


def test_detail_cache_metadata_is_saved_without_notifications(isolated_storage):
    # Değişiklik olmasa da detail_fetched_at kaydedilmeli; yoksa 30 dk sonra her
    # döngüde tüm ödev detayları yeniden çekilir.
    sent_messages, sent_buttons = isolated_storage
    url = "https://ninova.itu.edu.tr/Sinif/1"
    main._process_user_results(
        "1", "user", None, {url: _course(announcements=[])}, silent=True, include_reminders=False
    )

    refreshed = _course(announcements=[])
    refreshed["assignments"][0]["detail_fetched_at"] = 12345.0
    changes = main._process_user_results(
        "1", "user", None, {url: refreshed}, silent=False, include_reminders=False
    )

    assert changes == []
    assert sent_messages == []
    assert sent_buttons == []
    saved = storage.load_saved_grades()["1"][url]["assignments"][0]
    assert saved["detail_fetched_at"] == 12345.0


def test_suspect_empty_file_counter_is_persisted(isolated_storage):
    # Regresyon: ilk şüpheli boş dosya listesinde sayaç artıyor ama değişiklik
    # olmadığı için kaydedilmiyordu; gerçekten silinen dosyalar asla kabul edilmiyordu.
    sent_messages, _ = isolated_storage
    url = "https://ninova.itu.edu.tr/Sinif/1"
    main._process_user_results(
        "1", "user", None, {url: _course(announcements=[])}, silent=True, include_reminders=False
    )

    changes = main._process_user_results(
        "1",
        "user",
        None,
        {url: _course(announcements=[], files=[])},
        silent=False,
        include_reminders=False,
    )

    assert changes == []
    assert sent_messages == []
    saved = storage.load_saved_grades()["1"][url]
    assert saved["files_suspect_count"] == 1
    assert saved["files"][0]["name"] == "a.pdf"


def test_course_removed_during_check_is_not_written_back(isolated_storage):
    # Regresyon: tarama sürerken takipten çıkarılan ders, tarama sonucu kaydedilince
    # ninova_data.json'a geri yazılıyordu (ders menüde yeniden görünüyordu).
    sent_messages, _ = isolated_storage
    url = "https://ninova.itu.edu.tr/Sinif/1"
    storage.modify_user("1", lambda data: data.__setitem__("urls", []))

    changes = main._process_user_results(
        "1",
        "user",
        None,
        {url: _course(announcements=[])},
        silent=False,
        include_reminders=False,
    )

    assert "1" not in storage.load_saved_grades()
    assert changes  # değişiklikler hesaplandı ama kaydedilmedi
    assert sent_messages  # bildirim tarama sonucuna göre gider


@pytest.mark.usefixtures("isolated_storage")
def test_deleted_user_grades_are_not_recreated():
    url = "https://ninova.itu.edu.tr/Sinif/1"
    storage.delete_user("1")

    main._process_user_results(
        "1", "user", None, {url: _course(announcements=[])}, silent=True, include_reminders=False
    )

    assert storage.load_saved_grades() == {}


@pytest.mark.usefixtures("isolated_storage")
def test_touch_last_check_does_not_recreate_deleted_user():
    storage.save_all_users({"2": {"username": "x"}})

    main._touch_last_check("1")
    main._touch_last_check("2")

    users = storage.load_all_users()
    assert "1" not in users
    assert "last_check" in users["2"]
