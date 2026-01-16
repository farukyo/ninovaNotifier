"""
Tests for common/cache.py module.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLoadFileCache:
    """Tests for load_file_cache function."""

    def test_load_from_existing_file(self, temp_dir):
        """Test loading cache from existing file."""
        import common.cache

        cache_file = os.path.join(temp_dir, "file_cache.json")
        test_data = {"https://ninova.itu.edu.tr/file1": "file_id_123"}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {}

        result = common.cache.load_file_cache()

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert result == test_data

    def test_load_returns_empty_when_file_missing(self, temp_dir):
        """Test loading returns empty dict when file doesn't exist."""
        import common.cache

        nonexistent = os.path.join(temp_dir, "nonexistent.json")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = nonexistent
        common.cache._FILE_CACHE = {}

        result = common.cache.load_file_cache()

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert result == {}

    def test_load_handles_invalid_json(self, temp_dir):
        """Test loading handles invalid JSON gracefully."""
        import common.cache

        cache_file = os.path.join(temp_dir, "invalid.json")
        with open(cache_file, "w") as f:
            f.write("not valid json {{{")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {}

        result = common.cache.load_file_cache()

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert result == {}


class TestSaveFileCache:
    """Tests for save_file_cache function."""

    def test_save_cache_to_file(self, temp_dir):
        """Test saving cache to file."""
        import common.cache

        cache_file = os.path.join(temp_dir, "save_test.json")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {"url1": "id1", "url2": "id2"}

        common.cache.save_file_cache()

        # Read back and verify
        with open(cache_file, encoding="utf-8") as f:
            saved_data = json.load(f)

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert saved_data == {"url1": "id1", "url2": "id2"}

    def test_save_creates_directory(self, temp_dir):
        """Test that save creates parent directory if needed."""
        import common.cache

        cache_file = os.path.join(temp_dir, "subdir", "cache.json")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {"test": "data"}

        common.cache.save_file_cache()

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert os.path.exists(cache_file)


class TestGetCachedFileId:
    """Tests for get_cached_file_id function."""

    def test_get_existing_cached_id(self, temp_dir):  # noqa: ARG002
        """Test getting an existing cached file ID."""
        import common.cache

        original_cache = common.cache._FILE_CACHE
        common.cache._FILE_CACHE = {"https://ninova.itu.edu.tr/file1": "cached_id_123"}

        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/file1")

        common.cache._FILE_CACHE = original_cache

        assert result == "cached_id_123"

    def test_get_nonexistent_id_returns_none(self, temp_dir):  # noqa: ARG002
        """Test getting nonexistent ID returns None."""
        import common.cache

        original_cache = common.cache._FILE_CACHE
        common.cache._FILE_CACHE = {"other_url": "id"}

        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/nonexistent")

        common.cache._FILE_CACHE = original_cache

        assert result is None

    def test_auto_loads_cache_if_empty(self, temp_dir):
        """Test auto-loading cache when empty."""
        import common.cache

        cache_file = os.path.join(temp_dir, "auto_load.json")
        test_data = {"https://ninova.itu.edu.tr/auto": "auto_id"}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {}  # Empty to trigger auto-load

        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/auto")

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

        assert result == "auto_id"


class TestSetCachedFileId:
    """Tests for set_cached_file_id function."""

    def test_set_and_save_cached_id(self, temp_dir):
        """Test setting a cached file ID."""
        import common.cache

        cache_file = os.path.join(temp_dir, "set_test.json")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {}

        common.cache.set_cached_file_id("https://ninova.itu.edu.tr/new_file", "new_id_456")

        # Verify in memory
        assert common.cache._FILE_CACHE["https://ninova.itu.edu.tr/new_file"] == "new_id_456"

        # Verify on disk
        with open(cache_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["https://ninova.itu.edu.tr/new_file"] == "new_id_456"

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache

    def test_set_overwrites_existing(self, temp_dir):
        """Test that setting overwrites existing cached ID."""
        import common.cache

        cache_file = os.path.join(temp_dir, "overwrite.json")

        original_cache_file = common.cache.CACHE_FILE
        original_cache = common.cache._FILE_CACHE
        common.cache.CACHE_FILE = cache_file
        common.cache._FILE_CACHE = {"url": "old_id"}

        common.cache.set_cached_file_id("url", "new_id")

        assert common.cache._FILE_CACHE["url"] == "new_id"

        common.cache.CACHE_FILE = original_cache_file
        common.cache._FILE_CACHE = original_cache
