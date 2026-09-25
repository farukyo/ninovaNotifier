"""Tests for core/error_tracker.py — thresholds, recovery messages, thread safety."""

import threading

import pytest

from core import error_tracker


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(error_tracker, "_ERROR_TRACKER_FILE", tmp_path / "error_tracker.json")
    monkeypatch.setattr(error_tracker, "_tracker", {})
    monkeypatch.setattr(error_tracker, "ADMIN_TELEGRAM_IDS", [99])
    monkeypatch.setattr(
        error_tracker,
        "send_telegram_message",
        lambda chat_id, msg, **_kw: sent.append((chat_id, msg)),
    )
    return sent


def test_thresholds_notify_admin_and_user_once(tracker):
    for _ in range(error_tracker.ERROR_THRESHOLD_USER + 2):
        error_tracker.record_error("1", "NETWORK_TIMEOUT", "<timeout & retry>", "user")

    recipients = [chat_id for chat_id, _msg in tracker]
    assert recipients.count(99) == 1
    assert recipients.count("1") == 1
    # Hata detayı HTML olarak kaçırılmalı (aksi halde Telegram mesajı reddeder).
    assert "&lt;timeout &amp; retry&gt;" in tracker[0][1]


def test_record_success_sends_recovery_and_resets(tracker):
    for _ in range(error_tracker.ERROR_THRESHOLD_USER):
        error_tracker.record_error("1", "NETWORK_TIMEOUT", "x", "user")
    tracker.clear()

    error_tracker.record_success("1", "user")
    error_tracker.record_success("1", "user")

    assert sorted(str(chat_id) for chat_id, _ in tracker) == ["1", "99"]
    assert error_tracker._tracker["1"]["error_count"] == 0


@pytest.mark.usefixtures("tracker")
def test_concurrent_record_error_is_consistent():
    # Regresyon: _tracker kilitsiz değiştiriliyordu; json.dump sırasında sözlük
    # değişirse "dictionary changed size during iteration" hatası oluşabiliyordu.
    errors = []

    def worker(n):
        try:
            for _ in range(20):
                error_tracker.record_error(str(n % 4), "X", "y", "u")
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sum(entry["error_count"] for entry in error_tracker._tracker.values()) == 160
