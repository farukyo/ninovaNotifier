"""
Tests for bot/utils.py module.
"""

import urllib.parse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEncodePath:
    """Tests for encode_path function."""

    def test_encode_simple_path(self):
        """Test encoding a simple path."""
        from bot.utils import encode_path

        result = encode_path(["folder1", "folder2"])
        decoded = urllib.parse.unquote(result)
        assert decoded == "folder1/folder2"

    def test_encode_empty_path(self):
        """Test encoding an empty path."""
        from bot.utils import encode_path

        result = encode_path([])
        assert result == ""

    def test_encode_single_segment(self):
        """Test encoding a single segment path."""
        from bot.utils import encode_path

        result = encode_path(["documents"])
        decoded = urllib.parse.unquote(result)
        assert decoded == "documents"

    def test_encode_path_with_special_chars(self):
        """Test encoding path with special characters."""
        from bot.utils import encode_path

        result = encode_path(["folder with spaces", "file&name"])
        # Should be URL encoded
        assert " " not in result or "%20" in result
        assert "&" not in result or "%26" in result

    def test_encode_path_with_turkish_chars(self):
        """Test encoding path with Turkish characters."""
        from bot.utils import encode_path

        result = encode_path(["ödevler", "şifre"])
        # Should be URL encoded
        assert "%" in result or result == urllib.parse.quote("ödevler/şifre")


class TestDecodePath:
    """Tests for decode_path function."""

    def test_decode_simple_path(self):
        """Test decoding a simple path."""
        from bot.utils import decode_path

        encoded = urllib.parse.quote("folder1/folder2")
        result = decode_path(encoded)
        assert result == ["folder1", "folder2"]

    def test_decode_empty_path(self):
        """Test decoding an empty path."""
        from bot.utils import decode_path

        result = decode_path("")
        assert result == []

    def test_decode_single_segment(self):
        """Test decoding a single segment."""
        from bot.utils import decode_path

        encoded = urllib.parse.quote("documents")
        result = decode_path(encoded)
        assert result == ["documents"]

    def test_decode_path_with_special_chars(self):
        """Test decoding path with special characters."""
        from bot.utils import decode_path

        encoded = urllib.parse.quote("folder with spaces/file&name")
        result = decode_path(encoded)
        assert result == ["folder with spaces", "file&name"]

    def test_decode_path_filters_empty_segments(self):
        """Test decoding filters out empty segments."""
        from bot.utils import decode_path

        encoded = urllib.parse.quote("folder1//folder2")
        result = decode_path(encoded)
        assert "" not in result


class TestEncodeDecodeRoundtrip:
    """Tests for encode/decode roundtrip."""

    def test_roundtrip_simple(self):
        """Test encode then decode returns original."""
        from bot.utils import encode_path, decode_path

        original = ["folder1", "folder2", "folder3"]
        encoded = encode_path(original)
        decoded = decode_path(encoded)
        assert decoded == original

    def test_roundtrip_special_chars(self):
        """Test roundtrip with special characters."""
        from bot.utils import encode_path, decode_path

        original = ["folder with spaces", "file&name", "test=value"]
        encoded = encode_path(original)
        decoded = decode_path(encoded)
        assert decoded == original

    def test_roundtrip_turkish_chars(self):
        """Test roundtrip with Turkish characters."""
        from bot.utils import encode_path, decode_path

        original = ["ödevler", "çalışmalar", "üniteler"]
        encoded = encode_path(original)
        decoded = decode_path(encoded)
        assert decoded == original

    def test_roundtrip_empty(self):
        """Test roundtrip with empty list."""
        from bot.utils import encode_path, decode_path

        original = []
        encoded = encode_path(original)
        decoded = decode_path(encoded)
        assert decoded == original

    def test_roundtrip_deep_path(self):
        """Test roundtrip with deep nested path."""
        from bot.utils import encode_path, decode_path

        original = ["level1", "level2", "level3", "level4", "level5"]
        encoded = encode_path(original)
        decoded = decode_path(encoded)
        assert decoded == original
