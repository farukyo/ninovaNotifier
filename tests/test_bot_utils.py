"""
Tests for bot/utils.py module.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEncodePath:
    """Tests for encode_path function."""

    def test_encode_single_segment(self):
        """Test encoding a single segment."""
        from bot.utils import encode_path

        result = encode_path(["folder"])

        assert result == "folder"

    def test_encode_multiple_segments(self):
        """Test encoding multiple segments."""
        from bot.utils import encode_path

        result = encode_path(["ders", "notlar", "hafta1"])

        assert "%2F" in result or "/" not in result

    def test_encode_empty_list(self):
        """Test encoding empty list."""
        from bot.utils import encode_path

        result = encode_path([])

        assert result == ""

    def test_encode_special_characters(self):
        """Test encoding with Turkish characters."""
        from bot.utils import encode_path

        result = encode_path(["ders", "ödevler", "şablon"])

        # Should be URL encoded
        assert "%" in result


class TestDecodePath:
    """Tests for decode_path function."""

    def test_decode_single_segment(self):
        """Test decoding a single segment."""
        from bot.utils import decode_path

        result = decode_path("folder")

        assert result == ["folder"]

    def test_decode_multiple_segments(self):
        """Test decoding multiple segments."""
        from bot.utils import decode_path

        # URL encoded path with /
        encoded = "ders%2Fnotlar%2Fhafta1"
        result = decode_path(encoded)

        assert len(result) == 3
        assert result[0] == "ders"

    def test_decode_empty_string(self):
        """Test decoding empty string."""
        from bot.utils import decode_path

        result = decode_path("")

        assert result == []

    def test_encode_decode_roundtrip(self):
        """Test that encode and decode are inverse operations."""
        from bot.utils import decode_path, encode_path

        original = ["klasör1", "alt_klasör", "dosyalar"]
        encoded = encode_path(original)
        decoded = decode_path(encoded)

        assert decoded == original


class TestShowFileBrowser:
    """Tests for show_file_browser function."""

    @patch("bot.utils.bot")
    @patch("bot.utils.load_saved_grades")
    def test_returns_early_on_invalid_course_idx(self, mock_load, mock_bot):
        """Test returns early when course index is invalid."""
        from bot.utils import show_file_browser

        mock_load.return_value = {"12345": {"/course1": {"files": []}}}

        # Course idx 5 is out of range (only 1 course)
        show_file_browser("12345", 100, 5)

        mock_bot.edit_message_text.assert_not_called()

    @patch("bot.utils.bot")
    @patch("bot.utils.load_saved_grades")
    def test_shows_no_files_message(self, mock_load, mock_bot):
        """Test shows message when no files exist."""
        from bot.utils import show_file_browser

        mock_load.return_value = {
            "12345": {
                "/course1": {
                    "course_name": "Test Ders",
                    "files": [],
                }
            }
        }

        show_file_browser("12345", 100, 0)

        mock_bot.edit_message_text.assert_called_once()
        call_args = mock_bot.edit_message_text.call_args
        assert "Dosya bulunamadı" in call_args.kwargs["text"]

    @patch("bot.utils.bot")
    @patch("bot.utils.load_saved_grades")
    def test_shows_files_and_folders(self, mock_load, mock_bot):
        """Test shows files and folders correctly."""
        from bot.utils import show_file_browser

        mock_load.return_value = {
            "12345": {
                "/course1": {
                    "course_name": "Test Ders",
                    "files": [
                        {"name": "file1.pdf", "url": "/f1"},
                        {"name": "folder/file2.pdf", "url": "/f2"},
                    ],
                }
            }
        }

        show_file_browser("12345", 100, 0)

        mock_bot.edit_message_text.assert_called_once()
        call_args = mock_bot.edit_message_text.call_args
        assert "Dosyalar" in call_args.kwargs["text"]

    @patch("bot.utils.bot")
    @patch("bot.utils.load_saved_grades")
    def test_navigates_to_subfolder(self, mock_load, mock_bot):
        """Test navigating to a subfolder works."""
        from bot.utils import encode_path, show_file_browser

        mock_load.return_value = {
            "12345": {
                "/course1": {
                    "course_name": "Test Ders",
                    "files": [
                        {"name": "folder/subfile.pdf", "url": "/f1"},
                    ],
                }
            }
        }

        # Navigate to 'folder'
        path_str = encode_path(["folder"])
        show_file_browser("12345", 100, 0, path_str)

        mock_bot.edit_message_text.assert_called_once()
