"""
Tests for common/cache.py module.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLoadFileCache:
    """Tests for load_file_cache function."""
    
    def test_load_cache_no_file(self, temp_dir):
        """Test loading cache when file doesn't exist."""
        with patch('common.cache.CACHE_FILE', os.path.join(temp_dir, 'nonexistent.json')):
            import importlib
            import common.cache
            common.cache._FILE_CACHE = {}
            common.cache.CACHE_FILE = os.path.join(temp_dir, 'nonexistent.json')
            
            result = common.cache.load_file_cache()
            assert result == {}
    
    def test_load_cache_valid_file(self, mock_cache_file):
        """Test loading cache from valid file."""
        import common.cache
        common.cache._FILE_CACHE = {}
        common.cache.CACHE_FILE = mock_cache_file
        
        result = common.cache.load_file_cache()
        assert "https://ninova.itu.edu.tr/file1" in result
        assert result["https://ninova.itu.edu.tr/file1"] == "file_id_abc123"
    
    def test_load_cache_invalid_json(self, temp_dir):
        """Test loading cache with invalid JSON."""
        invalid_file = os.path.join(temp_dir, 'invalid.json')
        with open(invalid_file, 'w') as f:
            f.write("not valid json {{{")
        
        import common.cache
        common.cache._FILE_CACHE = {}
        common.cache.CACHE_FILE = invalid_file
        
        result = common.cache.load_file_cache()
        assert result == {}


class TestSaveFileCache:
    """Tests for save_file_cache function."""
    
    def test_save_cache_creates_file(self, temp_dir):
        """Test saving cache creates file."""
        cache_file = os.path.join(temp_dir, 'new_cache.json')
        
        import common.cache
        common.cache._FILE_CACHE = {"url1": "file_id_1"}
        common.cache.CACHE_FILE = cache_file
        
        common.cache.save_file_cache()
        
        assert os.path.exists(cache_file)
        with open(cache_file, 'r') as f:
            data = json.load(f)
        assert data == {"url1": "file_id_1"}
    
    def test_save_cache_updates_existing(self, mock_cache_file):
        """Test saving cache updates existing file."""
        import common.cache
        common.cache._FILE_CACHE = {"new_url": "new_id"}
        common.cache.CACHE_FILE = mock_cache_file
        
        common.cache.save_file_cache()
        
        with open(mock_cache_file, 'r') as f:
            data = json.load(f)
        assert data == {"new_url": "new_id"}


class TestGetCachedFileId:
    """Tests for get_cached_file_id function."""
    
    def test_get_existing_file_id(self, mock_cache_file):
        """Test getting an existing file ID from cache."""
        import common.cache
        common.cache._FILE_CACHE = {}
        common.cache.CACHE_FILE = mock_cache_file
        
        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/file1")
        assert result == "file_id_abc123"
    
    def test_get_nonexistent_file_id(self, mock_cache_file):
        """Test getting a non-existent file ID returns None."""
        import common.cache
        common.cache._FILE_CACHE = {}
        common.cache.CACHE_FILE = mock_cache_file
        
        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/nonexistent")
        assert result is None
    
    def test_get_loads_cache_if_empty(self, mock_cache_file):
        """Test that get loads cache if not already loaded."""
        import common.cache
        common.cache._FILE_CACHE = {}  # Empty cache
        common.cache.CACHE_FILE = mock_cache_file
        
        result = common.cache.get_cached_file_id("https://ninova.itu.edu.tr/file1")
        assert result == "file_id_abc123"
        assert common.cache._FILE_CACHE  # Cache should now be populated


class TestSetCachedFileId:
    """Tests for set_cached_file_id function."""
    
    def test_set_new_file_id(self, temp_dir):
        """Test setting a new file ID."""
        cache_file = os.path.join(temp_dir, 'cache.json')
        
        import common.cache
        common.cache._FILE_CACHE = {}
        common.cache.CACHE_FILE = cache_file
        
        # Create empty cache file first
        with open(cache_file, 'w') as f:
            json.dump({}, f)
        
        common.cache.set_cached_file_id("url1", "file_id_1")
        
        assert common.cache._FILE_CACHE["url1"] == "file_id_1"
        
        # Check file was saved
        with open(cache_file, 'r') as f:
            data = json.load(f)
        assert data["url1"] == "file_id_1"
    
    def test_set_updates_existing(self, mock_cache_file):
        """Test setting file ID updates existing entry."""
        import common.cache
        common.cache._FILE_CACHE = {"url1": "old_id"}
        common.cache.CACHE_FILE = mock_cache_file
        
        common.cache.set_cached_file_id("url1", "new_id")
        
        assert common.cache._FILE_CACHE["url1"] == "new_id"
