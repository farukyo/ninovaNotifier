"""
Tests for services/ninova/file_utils.py module.
"""
import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDownloadFile:
    """Tests for download_file function."""
    
    def test_download_to_buffer(self, mock_session):
        """Test downloading file to BytesIO buffer."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Disposition": 'attachment; filename="test.pdf"'}
        mock_response.iter_content.return_value = [b"file content"]
        mock_session.get.return_value = mock_response
        
        from services.ninova.file_utils import download_file
        
        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file/123",
            "default.pdf",
            to_buffer=True
        )
        
        assert result is not None
        assert isinstance(result, tuple)
        buffer, filename = result
        assert isinstance(buffer, BytesIO)
    
    def test_download_handles_redirect(self, mock_session):
        """Test handling 302 redirect (session expired)."""
        redirect_response = MagicMock()
        redirect_response.status_code = 302
        
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.iter_content.return_value = [b"content"]
        
        mock_session.get.side_effect = [redirect_response, success_response]
        
        from services.ninova.file_utils import download_file
        
        with patch('services.ninova.file_utils.login_to_ninova', return_value=True):
            result = download_file(
                mock_session,
                "https://ninova.itu.edu.tr/file/123",
                "test.pdf",
                chat_id="12345",
                username="user",
                password="pass",
                to_buffer=True
            )
        
        # Should have tried to login after redirect
        assert result is not None
    
    def test_download_fails_after_failed_login(self, mock_session):
        """Test that download fails if login fails after redirect."""
        redirect_response = MagicMock()
        redirect_response.status_code = 302
        
        mock_session.get.return_value = redirect_response
        
        from services.ninova.file_utils import download_file
        
        with patch('services.ninova.file_utils.login_to_ninova', return_value=False):
            result = download_file(
                mock_session,
                "https://ninova.itu.edu.tr/file/123",
                "test.pdf",
                chat_id="12345",
                username="user",
                password="pass",
                to_buffer=True
            )
        
        assert result is None
    
    def test_download_extracts_filename_from_header(self, mock_session):
        """Test extracting filename from Content-Disposition header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Disposition": 'attachment; filename="actual_filename.pdf"'
        }
        mock_response.iter_content.return_value = [b"content"]
        mock_session.get.return_value = mock_response
        
        from services.ninova.file_utils import download_file
        
        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file/123",
            "default.pdf",
            to_buffer=True
        )
        
        assert result is not None
        _, filename = result
        assert filename == "actual_filename.pdf"
    
    def test_download_handles_exception(self, mock_session):
        """Test handling exceptions during download."""
        mock_session.get.side_effect = Exception("Network error")
        
        from services.ninova.file_utils import download_file
        
        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file/123",
            "test.pdf",
            to_buffer=True
        )
        
        assert result is None
    
    def test_download_sanitizes_filename(self, mock_session):
        """Test that filename is sanitized."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Disposition": 'attachment; filename="file<>:name.pdf"'
        }
        mock_response.iter_content.return_value = [b"content"]
        mock_session.get.return_value = mock_response
        
        from services.ninova.file_utils import download_file
        
        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file/123",
            "default.pdf",
            to_buffer=True
        )
        
        assert result is not None
        _, filename = result
        # Special characters should be removed
        assert "<" not in filename
        assert ">" not in filename
        assert ":" not in filename
    
    def test_download_to_file(self, mock_session, temp_dir):
        """Test downloading file to disk."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Disposition": 'filename="test.pdf"'}
        mock_response.iter_content.return_value = [b"file content here"]
        mock_session.get.return_value = mock_response
        
        from services.ninova.file_utils import download_file
        
        # Change to temp dir
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            result = download_file(
                mock_session,
                "https://ninova.itu.edu.tr/file/123",
                "default.pdf",
                to_buffer=False
            )
            
            assert result is not None
            assert os.path.exists(result)
        finally:
            os.chdir(original_cwd)
    
    def test_download_empty_content_disposition(self, mock_session):
        """Test when Content-Disposition header is missing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b"content"]
        mock_session.get.return_value = mock_response
        
        from services.ninova.file_utils import download_file
        
        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file/123",
            "fallback.pdf",
            to_buffer=True
        )
        
        assert result is not None
        _, filename = result
        # Should use default filename
        assert filename == "fallback.pdf"
