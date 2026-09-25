"""Tests for helpers that used to have duplicate implementations."""

from cryptography.fernet import Fernet

from core import crypto
from core.cache import CacheManager
from core.utils import decrypt_password, encrypt_password, split_long_message
from services.ari24.client import Ari24Client


def test_password_roundtrip_via_utils_uses_crypto():
    token = encrypt_password("s3cret")
    assert token
    assert token != "s3cret"
    assert decrypt_password(token) == "s3cret"
    assert encrypt_password("") == ""
    assert decrypt_password("") == ""


def test_decrypt_with_wrong_key_returns_none():
    other = Fernet(Fernet.generate_key())
    assert crypto.decrypt_password(other, encrypt_password("x")) is None


def test_split_long_message_has_no_empty_chunks():
    # Regresyon: tam limit uzunluğundaki ilk satır boş bir parça üretiyordu.
    text = "a" * 10 + "\n" + "b" * 3
    chunks = split_long_message(text, limit=10)
    assert chunks == ["a" * 10, "b" * 3]
    assert all(chunks)


def test_split_long_message_splits_on_lines_and_long_lines():
    chunks = split_long_message("x" * 25, limit=10)
    assert chunks == ["x" * 10, "x" * 10, "x" * 5]


def test_ari24_month_parsing_is_case_insensitive():
    client = Ari24Client()
    assert client._parse_month("Ekim") == 10
    assert client._parse_month("EKİM") == 10
    assert client._parse_month("eki") == 10
    assert client._parse_month("ARALIK") == 12
    assert client._parse_month("Foo") is None


def test_cache_sync_persists_and_reloads(tmp_path):
    cache_file = tmp_path / "file_cache.json"
    cache = CacheManager(cache_file=cache_file)
    cache.set("https://f/1", "file-id-1")
    cache.sync()

    reloaded = CacheManager(cache_file=cache_file)
    assert reloaded.get("https://f/1") == "file-id-1"
    assert not list(tmp_path.glob("*.tmp"))
