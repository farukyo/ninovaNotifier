"""Tests for per-user session handling in core/config.py."""

from core import config


def test_close_user_session_also_drops_rehber_session():
    # Regresyon: Rehber oturumu hesap değişince kapatılmıyordu; yeni hesapla yapılan
    # aramalar 15 dakikaya kadar önceki hesabın Rehber girişini kullanabiliyordu.
    rehber_before = config.get_rehber_session("777")
    config.get_user_session("777")

    config.close_user_session("777")

    assert config.get_rehber_session("777") is not rehber_before
    config.close_user_session("777")


def test_rehber_and_ninova_sessions_are_separate():
    try:
        assert config.get_rehber_session("778") is not config.get_user_session("778")
    finally:
        config.close_user_session("778")
