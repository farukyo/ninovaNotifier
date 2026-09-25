"""Telegram callback_data is limited to 64 bytes (not characters)."""

from bot.handlers.user.ari24_commands import _club_key


def test_club_key_fits_telegram_limit_with_turkish_chars():
    club = "İTÜ Öğrenci Çağdaş Düşünce Güzel Sanatlar ve Şiir Kulübü Topluluğu"
    for prefix in ("sub_", "unsub_"):
        assert len(f"{prefix}{_club_key(club)}".encode()) <= 64


def test_club_key_is_stable_and_short_names_unchanged():
    assert _club_key("IEEE") == "IEEE"
    long_name = "ş" * 100
    assert _club_key(long_name) == _club_key(long_name)
    assert long_name.startswith(_club_key(long_name))
