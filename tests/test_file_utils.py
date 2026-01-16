"""
Tests for services/ninova/file_utils.py module.
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDownloadFile:
    """Tests for download_file function."""

    @patch("services.ninova.file_utils.login_to_ninova")
    def test_returns_none_on_failed_download(self, mock_login):  # noqa: ARG002
        """Test returns None on non-200 status."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        result = download_file(mock_session, "https://ninova.itu.edu.tr/file", "test.pdf")

        assert result is None

    @patch("services.ninova.file_utils.login_to_ninova")
    def test_handles_302_redirect_with_relogin(self, mock_login):
        """Test handles 302 redirect with re-login."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()

        # First call 302, second call 200
        mock_response_302 = MagicMock()
        mock_response_302.status_code = 302

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.headers = {"Content-Disposition": 'filename="downloaded.pdf"'}
        mock_response_200.iter_content = MagicMock(return_value=[b"content"])

        mock_session.get.side_effect = [mock_response_302, mock_response_200]
        mock_login.return_value = True

        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file",
            "test.pdf",
            chat_id="12345",
            username="user",
            password="pass",  # pragma: allowlist secret
            to_buffer=True,
        )

        assert result is not None
        assert isinstance(result[0], io.BytesIO)

    @patch("services.ninova.file_utils.login_to_ninova")
    def test_returns_buffer_when_to_buffer_true(self, mock_login):  # noqa: ARG002
        """Test returns BytesIO when to_buffer is True."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content = MagicMock(return_value=[b"file content"])
        mock_session.get.return_value = mock_response

        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file",
            "test.pdf",
            to_buffer=True,
        )

        assert result is not None
        buffer, filename = result
        assert isinstance(buffer, io.BytesIO)
        assert filename == "test.pdf"

    @patch("services.ninova.file_utils.login_to_ninova")
    def test_parses_content_disposition_filename(self, mock_login):  # noqa: ARG002
        """Test parsing filename from Content-Disposition header."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Disposition": 'attachment; filename="actual_name.pdf"'}
        mock_response.iter_content = MagicMock(return_value=[b"data"])
        mock_session.get.return_value = mock_response

        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file",
            "default.pdf",
            to_buffer=True,
        )

        assert result is not None
        _, filename = result
        assert "actual_name" in filename

    @patch("services.ninova.file_utils.login_to_ninova")
    def test_returns_none_on_login_failure(self, mock_login):
        """Test returns None when re-login fails."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()
        mock_response_302 = MagicMock()
        mock_response_302.status_code = 302
        mock_session.get.return_value = mock_response_302

        mock_login.return_value = False

        result = download_file(
            mock_session,
            "https://ninova.itu.edu.tr/file",
            "test.pdf",
            chat_id="12345",
        )

        assert result is None

    def test_returns_none_on_exception(self):
        """Test returns None on exception."""
        from services.ninova.file_utils import download_file

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")

        result = download_file(mock_session, "https://ninova.itu.edu.tr/file", "test.pdf")

        assert result is None
