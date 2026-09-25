"""Telegram callback_data is limited to 64 bytes (not characters)."""

from bot.handlers.user.ari24_commands import _club_key


def test_club_key_fits_telegram_limit_with_turkish_chars():
    club = "İTÜ Öğrenci Çağdaş Düşünce Güzel Sanatlar ve Şiir Kulübü Topluluğu"
    for prefix in ("sub_", "unsub_"):
        assert len(f"{prefix}{_club_key(club)}".encode()) <= 64


def test_club_key_is_stable_and_readable():
    assert _club_key("IEEE") == _club_key("IEEE")
    assert _club_key("IEEE").startswith("IEEE~")
    long_name = "ş" * 100
    assert long_name.startswith(_club_key(long_name).split("~")[0])


def test_club_keys_are_unique_for_names_sharing_a_long_prefix():
    # Regresyon: sadece önek kullanıldığında bu iki kulüp aynı anahtarı alıyordu ve
    # kullanıcı butondakinden farklı kulübe abone olabiliyordu.
    base = "İTÜ Öğrenci Çağdaş Düşünce Güzel Sanatlar ve Şiir Kulübü Topluluğu"
    assert _club_key(base + " A") != _club_key(base + " B")
