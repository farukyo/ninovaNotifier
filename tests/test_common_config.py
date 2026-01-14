"""
Tests for common/config.py module.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLoadAllUsers:
    """Tests for load_all_users function."""
    
    def test_load_users_file_exists(self, mock_users_file):
        """Test loading users from existing file."""
        with patch('common.config.USERS_FILE', mock_users_file):
            from common.config import load_all_users
            
            # Patch and reload to get updated path
            import common.config
            original_file = common.config.USERS_FILE
            common.config.USERS_FILE = mock_users_file
            
            result = common.config.load_all_users()
            
            common.config.USERS_FILE = original_file
            
            assert "12345" in result
            assert result["12345"]["username"] == "testuser"
    
    def test_load_users_no_file(self, temp_dir):
        """Test loading users when file doesn't exist returns empty dict."""
        import common.config
        original_file = common.config.USERS_FILE
        common.config.USERS_FILE = os.path.join(temp_dir, 'nonexistent.json')
        
        result = common.config.load_all_users()
        
        common.config.USERS_FILE = original_file
        
        assert result == {}
    
    def test_load_users_invalid_json(self, temp_dir):
        """Test loading users with invalid JSON returns empty dict."""
        invalid_file = os.path.join(temp_dir, 'invalid.json')
        with open(invalid_file, 'w') as f:
            f.write("not valid json")
        
        import common.config
        original_file = common.config.USERS_FILE
        common.config.USERS_FILE = invalid_file
        
        result = common.config.load_all_users()
        
        common.config.USERS_FILE = original_file
        
        assert result == {}


class TestSaveAllUsers:
    """Tests for save_all_users function."""
    
    def test_save_users_creates_file(self, temp_dir):
        """Test saving users creates file."""
        users_file = os.path.join(temp_dir, 'users.json')
        
        import common.config
        original_file = common.config.USERS_FILE
        common.config.USERS_FILE = users_file
        
        users = {"12345": {"username": "test", "password": "pass", "urls": []}}
        common.config.save_all_users(users)
        
        common.config.USERS_FILE = original_file
        
        assert os.path.exists(users_file)
        with open(users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data == users
    
    def test_save_users_preserves_unicode(self, temp_dir):
        """Test saving users preserves Turkish characters."""
        users_file = os.path.join(temp_dir, 'users.json')
        
        import common.config
        original_file = common.config.USERS_FILE
        common.config.USERS_FILE = users_file
        
        users = {"12345": {"username": "öğrenci", "password": "şifre", "urls": []}}
        common.config.save_all_users(users)
        
        common.config.USERS_FILE = original_file
        
        with open(users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["12345"]["username"] == "öğrenci"
    
    def test_save_and_load_roundtrip(self, temp_dir):
        """Test saving and loading preserves data."""
        users_file = os.path.join(temp_dir, 'users.json')
        
        import common.config
        original_file = common.config.USERS_FILE
        common.config.USERS_FILE = users_file
        
        users = {
            "12345": {"username": "user1", "password": "pass1", "urls": ["/url1"]},
            "67890": {"username": "user2", "password": "pass2", "urls": ["/url2", "/url3"]}
        }
        
        common.config.save_all_users(users)
        loaded = common.config.load_all_users()
        
        common.config.USERS_FILE = original_file
        
        assert loaded == users


class TestConfigConstants:
    """Tests for configuration constants."""
    
    def test_check_interval_is_positive(self):
        """Test CHECK_INTERVAL is a positive number."""
        from common.config import CHECK_INTERVAL
        
        assert CHECK_INTERVAL > 0
    
    def test_headers_has_user_agent(self):
        """Test HEADERS contains User-Agent."""
        from common.config import HEADERS
        
        assert "User-Agent" in HEADERS
        assert "Mozilla" in HEADERS["User-Agent"]
    
    def test_data_dir_exists(self):
        """Test DATA_DIR is defined."""
        from common.config import DATA_DIR
        
        assert DATA_DIR is not None
    
    def test_logs_dir_exists(self):
        """Test LOGS_DIR is defined."""
        from common.config import LOGS_DIR
        
        assert LOGS_DIR is not None
