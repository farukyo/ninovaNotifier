"""Tests for common/utils.py — encryption, date parsing, HTML sanitization, escape_html."""

import pytest
from cryptography.fernet import Fernet

# Patch cipher_suite before importing utils so we use a test key
_TEST_KEY = Fernet.generate_key()
_TEST_CIPHER = Fernet(_TEST_KEY)

import unittest.mock as mock

with mock.patch("common.config.cipher_suite", _TEST_CIPHER):
    from common.utils import (
        decrypt_password,
        encrypt_password,
        escape_html,
        get_file_icon,
        parse_turkish_date,
        sanitize_html_for_telegram,
    )


# ---------------------------------------------------------------------------
# parse_turkish_date
# ---------------------------------------------------------------------------


class TestParseTurkishDate:
    def test_full_date_lowercase(self):
        dt = parse_turkish_date("10 ekim 2025 14:30")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 10
        assert dt.day == 10
        assert dt.hour == 14
        assert dt.minute == 30

    def test_full_date_mixed_case(self):
        dt = parse_turkish_date("06 Ekim 2025 10:54")
        assert dt is not None
        assert dt.month == 10
        assert dt.day == 6

    def test_all_months(self):
        months = [
            ("ocak", 1),
            ("şubat", 2),
            ("mart", 3),
            ("nisan", 4),
            ("mayıs", 5),
            ("haziran", 6),
            ("temmuz", 7),
            ("ağustos", 8),
            ("eylül", 9),
            ("ekim", 10),
            ("kasım", 11),
            ("aralık", 12),
        ]
        for name, num in months:
            dt = parse_turkish_date(f"15 {name} 2024 00:00")
            assert dt is not None, f"Failed for month: {name}"
            assert dt.month == num

    def test_empty_string_returns_none(self):
        assert parse_turkish_date("") is None

    def test_invalid_format_returns_none(self):
        assert parse_turkish_date("invalid date string") is None

    def test_partial_data_returns_none(self):
        assert parse_turkish_date("10 ekim") is None


# ---------------------------------------------------------------------------
# escape_html
# ---------------------------------------------------------------------------


class TestEscapeHtml:
    def test_ampersand(self):
        assert escape_html("a & b") == "a &amp; b"

    def test_less_than(self):
        assert escape_html("a < b") == "a &lt; b"

    def test_greater_than(self):
        assert escape_html("a > b") == "a &gt; b"

    def test_combined(self):
        assert escape_html("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"

    def test_no_special_chars(self):
        assert escape_html("hello world") == "hello world"

    def test_empty_string(self):
        assert escape_html("") == ""


# ---------------------------------------------------------------------------
# sanitize_html_for_telegram
# ---------------------------------------------------------------------------


class TestSanitizeHtmlForTelegram:
    def test_empty_input(self):
        assert sanitize_html_for_telegram("") == ""

    def test_plain_text_escaped(self):
        result = sanitize_html_for_telegram("hello & world")
        assert "&amp;" in result

    def test_bold_preserved(self):
        result = sanitize_html_for_telegram("<b>bold text</b>")
        assert "<b>bold text</b>" in result

    def test_italic_preserved(self):
        result = sanitize_html_for_telegram("<i>italic</i>")
        assert "<i>italic</i>" in result

    def test_strong_becomes_bold(self):
        result = sanitize_html_for_telegram("<strong>text</strong>")
        assert "<b>text</b>" in result

    def test_link_preserved(self):
        result = sanitize_html_for_telegram('<a href="https://example.com">link</a>')
        assert 'href="https://example.com"' in result
        assert "link" in result

    def test_script_tag_stripped(self):
        result = sanitize_html_for_telegram("<script>alert('xss')</script>")
        assert "<script>" not in result

    def test_br_becomes_newline(self):
        result = sanitize_html_for_telegram("line1<br>line2")
        assert "\n" in result

    def test_ul_list_becomes_bullets(self):
        result = sanitize_html_for_telegram("<ul><li>item1</li><li>item2</li></ul>")
        assert "• item1" in result
        assert "• item2" in result

    def test_code_preserved(self):
        result = sanitize_html_for_telegram("<code>print()</code>")
        assert "<code>print()</code>" in result


# ---------------------------------------------------------------------------
# get_file_icon
# ---------------------------------------------------------------------------


class TestGetFileIcon:
    def test_pdf(self):
        assert get_file_icon("report.pdf") == "📕"

    def test_docx(self):
        assert get_file_icon("document.docx") == "📘"

    def test_python(self):
        assert get_file_icon("script.py") == "🐍"

    def test_zip(self):
        assert get_file_icon("archive.zip") == "📦"

    def test_jpg(self):
        assert get_file_icon("photo.jpg") == "🖼️"

    def test_unknown_extension(self):
        assert get_file_icon("file.xyz123") == "📄"

    def test_no_extension(self):
        assert get_file_icon("README") == "📄"

    def test_non_string_returns_default(self):
        assert get_file_icon(None) == "📄"
        assert get_file_icon(123) == "📄"
