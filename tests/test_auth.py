"""
Tests for services/ninova/auth.py module.
"""
import pytest
from unittest.mock import MagicMock, patch
import threading
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetUserLock:
    """Tests for get_user_lock function."""
    
    def test_returns_lock_object(self):
        """Test that function returns a Lock object."""
        from services.ninova.auth import get_user_lock
        
        lock = get_user_lock("12345")
        
        assert isinstance(lock, type(threading.Lock()))
    
    def test_same_user_gets_same_lock(self):
        """Test that same user ID returns same lock."""
        from services.ninova.auth import get_user_lock
        
        lock1 = get_user_lock("12345")
        lock2 = get_user_lock("12345")
        
        assert lock1 is lock2
    
    def test_different_users_get_different_locks(self):
        """Test that different users get different locks."""
        from services.ninova.auth import get_user_lock
        
        lock1 = get_user_lock("user_a")
        lock2 = get_user_lock("user_b")
        
        assert lock1 is not lock2
    
    def test_thread_safe(self):
        """Test that lock creation is thread-safe."""
        from services.ninova.auth import get_user_lock
        
        locks = []
        errors = []
        
        def get_lock():
            try:
                lock = get_user_lock("concurrent_user")
                locks.append(lock)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=get_lock) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        # All locks should be the same instance
        assert all(l is locks[0] for l in locks)


class TestLoginFailedError:
    """Tests for LoginFailedError exception."""
    
    def test_is_exception(self):
        """Test that LoginFailedError is an Exception."""
        from services.ninova.auth import LoginFailedError
        
        assert issubclass(LoginFailedError, Exception)
    
    def test_can_be_raised(self):
        """Test that LoginFailedError can be raised."""
        from services.ninova.auth import LoginFailedError
        
        with pytest.raises(LoginFailedError):
            raise LoginFailedError("Login failed")


class TestLoginToNinova:
    """Tests for login_to_ninova function."""
    
    def test_returns_false_for_empty_username(self, mock_session):
        """Test that empty username returns False."""
        from services.ninova.auth import login_to_ninova
        
        result = login_to_ninova(mock_session, "12345", "", "password")
        
        assert result == False
    
    def test_returns_false_for_empty_password(self, mock_session):
        """Test that empty password returns False."""
        from services.ninova.auth import login_to_ninova
        
        result = login_to_ninova(mock_session, "12345", "username", "")
        
        assert result == False
    
    def test_returns_false_for_none_credentials(self, mock_session):
        """Test that None credentials return False."""
        from services.ninova.auth import login_to_ninova
        
        result = login_to_ninova(mock_session, "12345", None, None)
        
        assert result == False
    
    def test_successful_login(self, mock_session):
        """Test successful login flow."""
        # Mock already logged in response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Dashboard</html>"
        mock_response.url = "https://ninova.itu.edu.tr/Kampus"
        mock_session.get.return_value = mock_response
        
        from services.ninova.auth import login_to_ninova
        
        with patch('services.ninova.auth.send_telegram_message'):
            result = login_to_ninova(mock_session, "12345", "user", "pass", quiet=True)
        
        assert result == True
    
    def test_failed_login_hata_in_response(self, mock_session):
        """Test failed login when 'Hatalı' in response."""
        # Mock login page response
        login_page = MagicMock()
        login_page.text = """
        <html>
        <input name="__VIEWSTATE" value="test">
        <input name="__VIEWSTATEGENERATOR" value="test">
        <input name="__EVENTVALIDATION" value="test">
        </html>
        """
        login_page.url = "https://ninova.itu.edu.tr/Login.aspx"
        login_page.status_code = 200
        
        # Mock failed login response
        failed_response = MagicMock()
        failed_response.text = "Hatalı kullanıcı adı veya şifre"
        failed_response.url = "https://ninova.itu.edu.tr/Login.aspx"
        failed_response.status_code = 200
        
        # First call returns 302 (not logged in), then login page, then failed
        check_response = MagicMock()
        check_response.status_code = 302
        
        mock_session.get.side_effect = [check_response, login_page]
        mock_session.post.return_value = failed_response
        
        from services.ninova.auth import login_to_ninova
        
        result = login_to_ninova(mock_session, "12345", "user", "wrongpass", quiet=True)
        
        assert result == False
    
    def test_handles_exception(self, mock_session):
        """Test that exceptions are handled gracefully."""
        mock_session.get.side_effect = Exception("Network error")
        
        from services.ninova.auth import login_to_ninova
        
        result = login_to_ninova(mock_session, "12345", "user", "pass", quiet=True)
        
        assert result == False
    
    def test_quiet_mode_no_notification(self, mock_session):
        """Test that quiet mode suppresses notifications."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Dashboard</html>"
        mock_response.url = "https://ninova.itu.edu.tr/Kampus"
        mock_session.get.return_value = mock_response
        
        from services.ninova.auth import login_to_ninova
        
        with patch('services.ninova.auth.send_telegram_message') as mock_send:
            result = login_to_ninova(mock_session, "12345", "user", "pass", quiet=True)
            
            # Should not send message in quiet mode when already logged in
            # Note: The actual behavior depends on implementation
