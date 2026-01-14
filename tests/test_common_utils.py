"""
Tests for common/utils.py module.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock
from io import BytesIO
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParseTurkishDate:
    """Tests for parse_turkish_date function."""

    def test_parse_valid_date_with_time(self):
        """Test parsing a valid Turkish date with time."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("10 Ekim 2025 14:30")
        assert result == datetime(2025, 10, 10, 14, 30)

    def test_parse_valid_date_midnight(self):
        """Test parsing a date at midnight."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("26 Aralık 2025 00:00")
        assert result == datetime(2025, 12, 26, 0, 0)

    def test_parse_date_all_months(self):
        """Test parsing dates for all Turkish months."""
        from common.utils import parse_turkish_date

        months_expected = [
            ("15 Ocak 2025 12:00", 1),
            ("15 Şubat 2025 12:00", 2),
            ("15 Mart 2025 12:00", 3),
            ("15 Nisan 2025 12:00", 4),
            ("15 Mayıs 2025 12:00", 5),
            ("15 Haziran 2025 12:00", 6),
            ("15 Temmuz 2025 12:00", 7),
            ("15 Ağustos 2025 12:00", 8),
            ("15 Eylül 2025 12:00", 9),
            ("15 Ekim 2025 12:00", 10),
            ("15 Kasım 2025 12:00", 11),
            ("15 Aralık 2025 12:00", 12),
        ]

        for date_str, expected_month in months_expected:
            result = parse_turkish_date(date_str)
            assert result is not None, f"Failed to parse: {date_str}"
            assert result.month == expected_month, f"Wrong month for: {date_str}"

    def test_parse_empty_string(self):
        """Test parsing an empty string returns None."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("")
        assert result is None

    def test_parse_invalid_format(self):
        """Test parsing invalid format returns None."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("2025-10-15")
        assert result is None

    def test_parse_incomplete_date(self):
        """Test parsing incomplete date returns None."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("10 Ekim")
        assert result is None

    def test_parse_unknown_month(self):
        """Test parsing unknown month defaults to January."""
        from common.utils import parse_turkish_date

        result = parse_turkish_date("10 UnknownMonth 2025 10:00")
        assert result is not None
        assert result.month == 1  # Defaults to January

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive for month names."""
        from common.utils import parse_turkish_date

        result1 = parse_turkish_date("10 EKIM 2025 10:00")
        result2 = parse_turkish_date("10 ekim 2025 10:00")
        result3 = parse_turkish_date("10 Ekim 2025 10:00")

        assert result1 == result2 == result3


class TestEncryptDecryptPassword:
    """Tests for encrypt_password and decrypt_password functions."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypting and decrypting returns original password."""
        from common.utils import encrypt_password, decrypt_password

        original = "my_secret_password123"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original

    def test_encrypt_empty_password(self):
        """Test encrypting empty password returns empty string."""
        from common.utils import encrypt_password

        result = encrypt_password("")
        assert result == ""

    def test_decrypt_empty_password(self):
        """Test decrypting empty password returns empty string."""
        from common.utils import decrypt_password

        result = decrypt_password("")
        assert result == ""

    def test_encrypt_none_password(self):
        """Test encrypting None returns empty string."""
        from common.utils import encrypt_password

        result = encrypt_password(None)
        assert result == ""

    def test_decrypt_invalid_token(self):
        """Test decrypting invalid token returns original value."""
        from common.utils import decrypt_password

        invalid = "not_a_valid_encrypted_token"
        result = decrypt_password(invalid)
        assert result == invalid

    def test_encrypt_unicode_password(self):
        """Test encrypting password with Turkish characters."""
        from common.utils import encrypt_password, decrypt_password

        original = "şifre_türkçe_öğrenci123"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original

    def test_encrypt_long_password(self):
        """Test encrypting a very long password."""
        from common.utils import encrypt_password, decrypt_password

        original = "a" * 1000
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)

        assert decrypted == original


class TestEscapeHtml:
    """Tests for escape_html function."""

    def test_escape_ampersand(self):
        """Test escaping ampersand."""
        from common.utils import escape_html

        result = escape_html("Tom & Jerry")
        assert result == "Tom &amp; Jerry"

    def test_escape_less_than(self):
        """Test escaping less than sign."""
        from common.utils import escape_html

        result = escape_html("5 < 10")
        assert result == "5 &lt; 10"

    def test_escape_greater_than(self):
        """Test escaping greater than sign."""
        from common.utils import escape_html

        result = escape_html("10 > 5")
        assert result == "10 &gt; 5"

    def test_escape_multiple_special_chars(self):
        """Test escaping multiple special characters."""
        from common.utils import escape_html

        result = escape_html("<script>alert('XSS & attack')</script>")
        assert result == "&lt;script&gt;alert('XSS &amp; attack')&lt;/script&gt;"

    def test_escape_normal_text(self):
        """Test that normal text is unchanged."""
        from common.utils import escape_html

        text = "Normal text without special chars"
        result = escape_html(text)
        assert result == text


class TestSanitizeHtmlForTelegram:
    """Tests for sanitize_html_for_telegram function."""

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string returns empty."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("")
        assert result == ""

    def test_sanitize_none(self):
        """Test sanitizing None returns empty."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram(None)
        assert result == ""

    def test_sanitize_plain_text(self):
        """Test plain text with no tags is escaped."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("Hello World")
        assert result == "Hello World"

    def test_sanitize_bold_tag(self):
        """Test bold tags are preserved."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<b>Bold</b>")
        assert result == "<b>Bold</b>"

    def test_sanitize_strong_to_bold(self):
        """Test strong tags are converted to bold."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<strong>Strong</strong>")
        assert result == "<b>Strong</b>"

    def test_sanitize_italic_tag(self):
        """Test italic tags are preserved."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<i>Italic</i>")
        assert result == "<i>Italic</i>"

    def test_sanitize_em_to_italic(self):
        """Test em tags are converted to italic."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<em>Emphasis</em>")
        assert result == "<i>Emphasis</i>"

    def test_sanitize_link(self):
        """Test link tags are preserved with href."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram('<a href="https://example.com">Link</a>')
        assert 'href="https://example.com"' in result
        assert ">Link<" in result

    def test_sanitize_br_tag(self):
        """Test br tags are converted to newlines."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("Line1<br>Line2")
        assert "\n" in result

    def test_sanitize_paragraph(self):
        """Test paragraph tags add spacing."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<p>Paragraph 1</p><p>Paragraph 2</p>")
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_sanitize_list(self):
        """Test list items are converted to bullet points."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<ul><li>Item 1</li><li>Item 2</li></ul>")
        assert "• Item 1" in result
        assert "• Item 2" in result

    def test_sanitize_nested_tags(self):
        """Test nested tags are handled correctly."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<b><i>Bold Italic</i></b>")
        assert "<b>" in result
        assert "<i>" in result

    def test_sanitize_code_tag(self):
        """Test code tags are preserved."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<code>print('hello')</code>")
        assert "<code>" in result


class TestGetFileIcon:
    """Tests for get_file_icon function."""

    def test_pdf_icon(self):
        """Test PDF files get book emoji."""
        from common.utils import get_file_icon

        result = get_file_icon("document.pdf")
        assert result == "📕"

    def test_word_icon(self):
        """Test Word files get document emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("report.doc") == "📘"
        assert get_file_icon("report.docx") == "📘"

    def test_excel_icon(self):
        """Test Excel files get spreadsheet emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("data.xlsx") == "📗"
        assert get_file_icon("data.xls") == "📗"
        assert get_file_icon("data.csv") == "📗"

    def test_powerpoint_icon(self):
        """Test PowerPoint files get presentation emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("slides.ppt") == "📙"
        assert get_file_icon("slides.pptx") == "📙"

    def test_archive_icon(self):
        """Test archive files get package emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("files.zip") == "📦"
        assert get_file_icon("files.rar") == "📦"
        assert get_file_icon("files.7z") == "📦"

    def test_image_icon(self):
        """Test image files get picture emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("photo.jpg") == "🖼️"
        assert get_file_icon("photo.png") == "🖼️"
        assert get_file_icon("photo.gif") == "🖼️"

    def test_video_icon(self):
        """Test video files get movie emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("video.mp4") == "🎬"
        assert get_file_icon("video.avi") == "🎬"

    def test_audio_icon(self):
        """Test audio files get music emoji."""
        from common.utils import get_file_icon

        assert get_file_icon("song.mp3") == "🎵"
        assert get_file_icon("sound.wav") == "🎵"

    def test_python_icon(self):
        """Test Python files get snake emoji."""
        from common.utils import get_file_icon

        result = get_file_icon("script.py")
        assert result == "🐍"

    def test_unknown_extension(self):
        """Test unknown extension returns default icon."""
        from common.utils import get_file_icon

        result = get_file_icon("file.xyz")
        assert result == "📄"

    def test_no_extension(self):
        """Test file without extension returns default icon."""
        from common.utils import get_file_icon

        result = get_file_icon("README")
        assert result == "📄"

    def test_case_insensitive(self):
        """Test extension matching is case insensitive."""
        from common.utils import get_file_icon

        assert get_file_icon("file.PDF") == "📕"
        assert get_file_icon("file.Pdf") == "📕"

    def test_non_string_input(self):
        """Test non-string input returns default icon."""
        from common.utils import get_file_icon

        assert get_file_icon(None) == "📄"
        assert get_file_icon(123) == "📄"
        assert get_file_icon([]) == "📄"


class TestSendTelegramMessage:
    """Tests for send_telegram_message function."""

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_send_simple_message(self, mock_post):
        """Test sending a simple message."""
        from common.utils import send_telegram_message

        mock_post.return_value.status_code = 200

        send_telegram_message("12345", "Hello World")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["chat_id"] == "12345"
        assert call_args[1]["json"]["text"] == "Hello World"

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_send_error_message(self, mock_post):
        """Test sending an error message adds prefix."""
        from common.utils import send_telegram_message

        mock_post.return_value.status_code = 200

        send_telegram_message("12345", "Error occurred", is_error=True)

        call_args = mock_post.call_args
        assert "⚠️" in call_args[1]["json"]["text"]
        assert "HATA" in call_args[1]["json"]["text"]

    @patch("common.utils.TELEGRAM_TOKEN", None)
    def test_no_token_does_nothing(self):
        """Test that missing token prevents sending."""
        from common.utils import send_telegram_message

        # Should not raise, just return
        send_telegram_message("12345", "Hello")

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_long_message_split(self, mock_post):
        """Test that long messages are split."""
        from common.utils import send_telegram_message

        mock_post.return_value.status_code = 200

        long_message = "A" * 5000  # Over 3500 limit
        send_telegram_message("12345", long_message)

        # Should be called multiple times
        assert mock_post.call_count >= 2


class TestSendTelegramDocument:
    """Tests for send_telegram_document function."""

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_send_by_file_id(self, mock_post, mock_telegram_response):
        """Test sending document by file ID."""
        from common.utils import send_telegram_document

        mock_post.return_value = mock_telegram_response

        send_telegram_document("12345", "file_abc123", is_file_id=True)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["data"]["document"] == "file_abc123"

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_send_by_buffer(self, mock_post, mock_telegram_response):
        """Test sending document from BytesIO buffer."""
        from common.utils import send_telegram_document

        mock_post.return_value = mock_telegram_response

        buffer = BytesIO(b"file content")
        send_telegram_document("12345", buffer, filename="test.txt")

        mock_post.assert_called_once()

    @patch("common.utils.TELEGRAM_TOKEN", None)
    def test_no_token_returns_none(self):
        """Test that missing token returns None."""
        from common.utils import send_telegram_document

        result = send_telegram_document("12345", "document")
        assert result is None

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_return_file_id(self, mock_post, mock_telegram_response):
        """Test that file_id is returned on success."""
        from common.utils import send_telegram_document

        mock_post.return_value = mock_telegram_response

        buffer = BytesIO(b"content")
        result = send_telegram_document("12345", buffer, filename="test.pdf")

        assert result == "test_file_id_12345"


class TestLoadSaveGrades:
    """Tests for load_saved_grades and save_grades functions."""

    def test_load_grades_file_exists(self, temp_dir):
        """Test loading grades from existing file."""
        import json

        grades_file = os.path.join(temp_dir, "grades.json")
        test_data = {"12345": {"course": "Test"}}
        with open(grades_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        with patch("common.utils.DATA_FILE", grades_file):
            with patch("common.utils.os.path.exists", return_value=True):
                # Direct test of the logic
                import common.utils

                original = common.utils.DATA_FILE
                common.utils.DATA_FILE = grades_file

                result = common.utils.load_saved_grades()

                common.utils.DATA_FILE = original
                assert result == test_data

    def test_load_grades_no_file(self, temp_dir):
        """Test loading grades when file doesn't exist returns empty dict."""
        import common.utils

        original = common.utils.DATA_FILE
        common.utils.DATA_FILE = os.path.join(temp_dir, "nonexistent.json")

        result = common.utils.load_saved_grades()

        common.utils.DATA_FILE = original
        assert result == {}

    def test_load_grades_invalid_json(self, temp_dir):
        """Test loading grades with invalid JSON returns empty dict."""
        import common.utils

        invalid_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_file, "w") as f:
            f.write("not valid json {{{")

        original = common.utils.DATA_FILE
        common.utils.DATA_FILE = invalid_file

        result = common.utils.load_saved_grades()

        common.utils.DATA_FILE = original
        assert result == {}

    def test_save_and_load_roundtrip(self, temp_dir):
        """Test saving and loading grades preserves data."""
        import common.utils

        grades_file = os.path.join(temp_dir, "grades.json")
        original = common.utils.DATA_FILE
        common.utils.DATA_FILE = grades_file

        test_data = {"user1": {"grades": [{"name": "Midterm", "grade": "85"}]}}
        common.utils.save_grades(test_data)
        loaded = common.utils.load_saved_grades()

        common.utils.DATA_FILE = original
        assert loaded == test_data


class TestUpdateUserData:
    """Tests for update_user_data function."""

    def test_update_existing_user(self, temp_dir):
        """Test updating an existing user's data."""
        import json
        import common.utils
        import common.config

        users_file = os.path.join(temp_dir, "users.json")
        initial_users = {"12345": {"username": "old_user", "password": "", "urls": []}}
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(initial_users, f)

        original = common.config.USERS_FILE
        common.config.USERS_FILE = users_file

        result = common.utils.update_user_data("12345", "username", "new_user")

        common.config.USERS_FILE = original
        assert result["username"] == "new_user"

    def test_update_new_user(self, temp_dir):
        """Test updating creates new user if not exists."""
        import json
        import common.utils
        import common.config

        users_file = os.path.join(temp_dir, "users.json")
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump({}, f)

        original = common.config.USERS_FILE
        common.config.USERS_FILE = users_file

        result = common.utils.update_user_data("99999", "username", "brand_new_user")

        common.config.USERS_FILE = original
        assert result["username"] == "brand_new_user"

    def test_update_password_encrypts(self, temp_dir):
        """Test that updating password encrypts it."""
        import json
        import common.utils
        import common.config

        users_file = os.path.join(temp_dir, "users.json")
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump({}, f)

        original = common.config.USERS_FILE
        common.config.USERS_FILE = users_file

        result = common.utils.update_user_data("12345", "password", "secret123")

        common.config.USERS_FILE = original
        # Password should be encrypted, not plain text
        assert result["password"] != "secret123"
        assert len(result["password"]) > 0


class TestSendTelegramMessageAdvanced:
    """Advanced tests for send_telegram_message function."""

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_very_long_single_line(self, mock_post):
        """Test message with a single line longer than limit."""
        from common.utils import send_telegram_message

        mock_post.return_value.status_code = 200

        # Single line over 3500 chars
        long_line = "X" * 4000
        send_telegram_message("12345", long_line)

        # Should split the single line
        assert mock_post.call_count >= 2

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_api_error_response(self, mock_post):
        """Test handling API error response."""
        from common.utils import send_telegram_message

        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Bad Request"

        # Should not raise, just log
        send_telegram_message("12345", "Test message")

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_api_exception(self, mock_post):
        """Test handling API exception."""
        from common.utils import send_telegram_message

        mock_post.side_effect = Exception("Network error")

        # Should not raise, just log
        send_telegram_message("12345", "Test message")

    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_empty_chat_id(self):
        """Test with empty chat_id does nothing."""
        from common.utils import send_telegram_message

        # Should not raise
        send_telegram_message("", "Test message")
        send_telegram_message(None, "Test message")


class TestSendTelegramDocumentAdvanced:
    """Advanced tests for send_telegram_document function."""

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_send_by_file_path(self, mock_post, temp_dir):
        """Test sending document by file path."""
        from common.utils import send_telegram_document

        # Create a temp file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"document": {"file_id": "abc123"}},
        }
        mock_post.return_value = mock_response

        result = send_telegram_document("12345", test_file)

        mock_post.assert_called_once()
        assert result == "abc123"

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_api_error(self, mock_post):
        """Test handling API error."""
        from common.utils import send_telegram_document

        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Bad Request"

        buffer = BytesIO(b"content")
        result = send_telegram_document("12345", buffer, filename="test.txt")

        assert result is None

    @patch("common.utils.requests.post")
    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_api_exception(self, mock_post):
        """Test handling API exception."""
        from common.utils import send_telegram_document

        mock_post.side_effect = Exception("Network error")

        buffer = BytesIO(b"content")
        result = send_telegram_document("12345", buffer, filename="test.txt")

        assert result is None

    @patch("common.utils.TELEGRAM_TOKEN", "test_token")
    def test_empty_chat_id(self):
        """Test with empty chat_id returns None."""
        from common.utils import send_telegram_document

        result = send_telegram_document("", "document")
        assert result is None


class TestSanitizeHtmlAdvanced:
    """Advanced tests for sanitize_html_for_telegram."""

    def test_underline_tag(self):
        """Test underline tags are preserved."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<u>Underlined</u>")
        assert "<u>" in result

    def test_strikethrough_tag(self):
        """Test strikethrough tags are converted."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<s>Strikethrough</s>")
        assert "<s>" in result

    def test_pre_tag(self):
        """Test pre tags are preserved."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<pre>code block</pre>")
        assert "<pre>" in result

    def test_link_without_href(self):
        """Test link without href."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<a>No href</a>")
        assert "No href" in result

    def test_link_without_text(self):
        """Test link without text uses href."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram('<a href="https://example.com"></a>')
        assert "example.com" in result

    def test_heading_tags(self):
        """Test heading tags add spacing."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<h1>Title</h1><h2>Subtitle</h2>")
        assert "Title" in result
        assert "Subtitle" in result

    def test_standalone_li_tag(self):
        """Test standalone li tag gets bullet."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<li>Item</li>")
        assert "•" in result

    def test_ins_tag(self):
        """Test ins tag converts to underline."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<ins>Inserted</ins>")
        assert "<u>" in result

    def test_del_tag(self):
        """Test del tag converts to strikethrough."""
        from common.utils import sanitize_html_for_telegram

        result = sanitize_html_for_telegram("<del>Deleted</del>")
        assert "<s>" in result
