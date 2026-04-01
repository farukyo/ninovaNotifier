"""Tests for bot/utils.py — validate_ninova_url (SSRF prevention)."""

import pytest

from bot.utils import validate_ninova_url


class TestValidateNinovaUrl:
    def test_valid_ninova_url(self):
        url = "https://ninova.itu.edu.tr/Kampus1/Dersler/12345"
        assert validate_ninova_url(url) is not None

    def test_www_variant_accepted(self):
        url = "https://www.ninova.itu.edu.tr/Kampus1/Dersler/12345"
        assert validate_ninova_url(url) is not None

    def test_empty_string_returns_none(self):
        assert validate_ninova_url("") is None

    def test_none_returns_none(self):
        assert validate_ninova_url(None) is None

    def test_external_domain_rejected(self):
        assert validate_ninova_url("https://evil.com/steal") is None

    def test_ssrf_internal_ip_rejected(self):
        assert validate_ninova_url("http://192.168.1.1/admin") is None

    def test_ssrf_localhost_rejected(self):
        assert validate_ninova_url("http://localhost/secret") is None

    def test_subdomain_bypass_rejected(self):
        # attacker.com/ninova.itu.edu.tr — netloc is attacker.com
        assert validate_ninova_url("https://attacker.com/ninova.itu.edu.tr") is None

    def test_suffix_stripped_notlar(self):
        url = "https://ninova.itu.edu.tr/Kampus1/Dersler/12345/Notlar"
        result = validate_ninova_url(url)
        assert result is not None
        assert not result.endswith("/Notlar")

    def test_suffix_stripped_duyurular(self):
        url = "https://ninova.itu.edu.tr/Kampus1/Dersler/12345/Duyurular"
        result = validate_ninova_url(url)
        assert result is not None
        assert not result.endswith("/Duyurular")

    def test_suffix_stripped_odevler(self):
        url = "https://ninova.itu.edu.tr/Kampus1/Dersler/12345/Odevler"
        result = validate_ninova_url(url)
        assert result is not None
        assert not result.endswith("/Odevler")

    def test_query_string_stripped(self):
        url = "https://ninova.itu.edu.tr/Kampus1/Dersler/12345?tab=1&foo=bar"
        result = validate_ninova_url(url)
        assert result is not None
        assert "?" not in result
