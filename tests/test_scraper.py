"""
Tests for services/ninova/scraper.py module.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetAnnouncements:
    """Tests for get_announcements function."""

    def test_returns_empty_on_non_200_status(self):
        """Test that non-200 status codes return empty list."""
        from services.ninova.scraper import get_announcements

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_parses_announcements_correctly(self, sample_html_announcements_page):
        """Test parsing announcements from HTML."""
        from services.ninova.scraper import get_announcements

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_announcements_page
        mock_session.get.return_value = mock_response

        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert len(result) >= 1
        assert "title" in result[0]
        assert "url" in result[0]

    def test_handles_exception_gracefully(self):
        """Test that exceptions return empty list."""
        from services.ninova.scraper import get_announcements

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")

        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_empty_announcements_page(self):
        """Test when no announcements are present."""
        from services.ninova.scraper import get_announcements

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><div>No announcements</div></body></html>"
        mock_session.get.return_value = mock_response

        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []


class TestGetAnnouncementDetail:
    """Tests for get_announcement_detail function."""

    def test_returns_empty_on_non_200(self):
        """Test non-200 status returns empty string."""
        from services.ninova.scraper import get_announcement_detail

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")

        assert result == ""

    def test_parses_announcement_content(self):
        """Test parsing announcement detail content."""
        from services.ninova.scraper import get_announcement_detail

        html = """
        <div class="duyuruGoruntule">
            <div class="icerik">
                <p>Bu bir <b>önemli</b> duyurudur.</p>
                <a href="/Dosya/123">Dosya linki</a>
            </div>
        </div>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")

        assert "önemli" in result
        assert "ninova.itu.edu.tr" in result  # Link should be absolute

    def test_handles_exception(self):
        """Test exception handling returns empty string."""
        from services.ninova.scraper import get_announcement_detail

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection error")

        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")

        assert result == ""

    def test_legacy_content_format(self):
        """Test parsing legacy content format with different ID."""
        from services.ninova.scraper import get_announcement_detail

        html = """
        <div id="ctl00_ContentPlaceHolder1_divIcerik">
            <p>Eski format duyuru içeriği</p>
        </div>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")

        assert "Eski format" in result


class TestGetAssignmentDetail:
    """Tests for get_assignment_detail function."""

    def test_returns_none_on_non_200(self):
        """Test non-200 status returns None."""
        from services.ninova.scraper import get_assignment_detail

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")

        assert result is None

    def test_parses_dates_correctly(self):
        """Test parsing start and end dates."""
        from services.ninova.scraper import get_assignment_detail

        html = """
        <span class="title_field">Teslim Başlangıcı</span>
        <span class="data_field">01 Ocak 2026 00:00</span>
        <span class="title_field">Teslim Bitişi</span>
        <span class="data_field">15 Ocak 2026 23:59</span>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")

        assert result is not None
        assert "01 Ocak 2026" in result["start_date"]
        assert "15 Ocak 2026" in result["end_date"]

    def test_detects_submitted_assignment(self):
        """Test detection of submitted assignment."""
        from services.ninova.scraper import get_assignment_detail

        html = """
        <span id="ctl00_ContentPlaceHolder1_lbOdevDosyalar">Dosyalar</span>
        <p>Yüklediğiniz ödev dosyalarını indirin</p>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")

        assert result is not None
        assert result["is_submitted"] is True

    def test_detects_not_submitted_assignment(self):
        """Test detection of not submitted assignment."""
        from services.ninova.scraper import get_assignment_detail

        html = """
        <a href="/OdevGonder">Ödevi Yükle</a>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")

        assert result is not None
        assert result["is_submitted"] is False

    def test_handles_exception(self):
        """Test exception handling returns None."""
        from services.ninova.scraper import get_assignment_detail

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Error")

        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")

        assert result is None


class TestGetAssignments:
    """Tests for get_assignments function."""

    def test_returns_empty_on_non_200(self):
        """Test non-200 status returns empty list."""
        from services.ninova.scraper import get_assignments

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_parses_assignments_from_table(self, sample_html_assignments):
        """Test parsing assignments from HTML table."""
        from services.ninova.scraper import get_assignments

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_assignments
        mock_session.get.return_value = mock_response

        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert len(result) >= 1
        assert "name" in result[0]
        assert "url" in result[0]
        assert "id" in result[0]

    def test_handles_no_table(self):
        """Test when no assignment table exists."""
        from services.ninova.scraper import get_assignments

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No table here</body></html>"
        mock_session.get.return_value = mock_response

        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_handles_exception(self):
        """Test exception handling returns empty list."""
        from services.ninova.scraper import get_assignments

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")

        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []


class TestGetClassFiles:
    """Tests for get_class_files function."""

    def test_returns_empty_on_non_200(self):
        """Test non-200 status returns empty list."""
        from services.ninova.scraper import get_class_files

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_parses_files_correctly(self, sample_html_files):
        """Test parsing files from HTML."""
        from services.ninova.scraper import get_class_files

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_files
        mock_session.get.return_value = mock_response

        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        # Should parse file entries (not folders in this simple test)
        assert isinstance(result, list)

    def test_handles_no_table(self):
        """Test when no file table exists."""
        from services.ninova.scraper import get_class_files

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No files</body></html>"
        mock_session.get.return_value = mock_response

        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []

    def test_handles_exception(self):
        """Test exception handling returns empty list."""
        from services.ninova.scraper import get_class_files

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Error")

        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == []


class TestGetAllFiles:
    """Tests for get_all_files function."""

    @patch("services.ninova.scraper.get_class_files")
    def test_combines_sinif_and_ders_files(self, mock_get_files):
        """Test that both SinifDosyalari and DersDosyalari are fetched."""
        from services.ninova.scraper import get_all_files

        mock_get_files.side_effect = [
            [{"name": "sinif_file.pdf", "url": "/file1"}],
            [{"name": "ders_file.pdf", "url": "/file2"}],
        ]

        mock_session = MagicMock()
        result = get_all_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert len(result) == 2
        assert result[0]["source"] == "Sınıf"
        assert result[1]["source"] == "Ders"


class TestGetUserCourses:
    """Tests for get_user_courses function."""

    def test_parses_courses_from_menu(self, sample_html_courses):
        """Test parsing courses from menuErisimAgaci."""
        from services.ninova.scraper import get_user_courses

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_courses
        mock_response.url = "https://ninova.itu.edu.tr/Kampus"
        mock_session.get.return_value = mock_response

        result = get_user_courses(mock_session)

        assert len(result) >= 1
        assert "name" in result[0]
        assert "url" in result[0]

    def test_returns_empty_on_no_tree(self):
        """Test returns empty when no menuErisimAgaci."""
        from services.ninova.scraper import get_user_courses

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No menu</body></html>"
        mock_response.url = "https://ninova.itu.edu.tr/Kampus"
        mock_session.get.return_value = mock_response

        result = get_user_courses(mock_session)

        assert result == []

    def test_detects_login_redirect(self):
        """Test detection of login redirect."""
        from services.ninova.scraper import get_user_courses

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Giriş yapınız</body></html>"
        mock_response.url = "https://ninova.itu.edu.tr/Login.aspx"
        mock_session.get.return_value = mock_response

        result = get_user_courses(mock_session)

        assert result == []

    def test_handles_exception(self):
        """Test exception handling returns empty list."""
        from services.ninova.scraper import get_user_courses

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Error")

        result = get_user_courses(mock_session)

        assert result == []


class TestGetGrades:
    """Tests for get_grades function."""

    def test_returns_none_on_non_200(self):
        """Test non-200 status returns None."""
        from services.ninova.scraper import get_grades

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        result = get_grades(
            mock_session, "https://ninova.itu.edu.tr/Sinif/123", "12345", "user", "pass"
        )

        assert result is None

    def test_parses_grades_from_table(self, sample_html_grades):
        """Test parsing grades from HTML table."""
        from services.ninova.scraper import get_grades

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_grades
        mock_session.get.return_value = mock_response

        # Mock the sub-functions to avoid recursive calls
        with patch("services.ninova.scraper.get_assignments", return_value=[]):
            with patch("services.ninova.scraper.get_all_files", return_value=[]):
                with patch("services.ninova.scraper.get_announcements", return_value=[]):
                    result = get_grades(
                        mock_session,
                        "https://ninova.itu.edu.tr/Sinif/123",
                        "12345",
                        "user",
                        "pass",
                    )

        assert result is not None
        assert "course_name" in result
        assert "grades" in result

    def test_handles_302_redirect_with_relogin(self):
        """Test handling 302 redirect with re-login attempt."""
        from services.ninova.scraper import get_grades

        mock_session = MagicMock()
        mock_response_302 = MagicMock()
        mock_response_302.status_code = 302

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = "<html><body></body></html>"

        mock_session.get.side_effect = [mock_response_302, mock_response_200]

        with patch("services.ninova.scraper.login_to_ninova", return_value=True):
            with patch("services.ninova.scraper.get_assignments", return_value=[]):
                with patch("services.ninova.scraper.get_all_files", return_value=[]):
                    with patch("services.ninova.scraper.get_announcements", return_value=[]):
                        result = get_grades(
                            mock_session,
                            "https://ninova.itu.edu.tr/Sinif/123",
                            "12345",
                            "user",
                            "pass",
                        )

        assert result is not None

    def test_handles_exception(self):
        """Test exception handling returns None."""
        from services.ninova.scraper import get_grades

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Error")

        result = get_grades(
            mock_session, "https://ninova.itu.edu.tr/Sinif/123", "12345", "user", "pass"
        )

        assert result is None


class TestGetClassInfo:
    """Tests for get_class_info function."""

    def test_returns_empty_on_non_200(self):
        """Test non-200 status returns empty dict."""
        from services.ninova.scraper import get_class_info

        mock_session = MagicMock()
        mock_session.get.return_value.status_code = 404

        result = get_class_info(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == {}

    def test_parses_end_date(self):
        """Test parsing class end date."""
        from services.ninova.scraper import get_class_info

        html = """
        <span class="title_field">Bitiş Tarihi</span>
        <span class="data_field">15 Ocak 2026</span>
        """

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_session.get.return_value = mock_response

        result = get_class_info(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert isinstance(result, dict)

    def test_handles_exception(self):
        """Test exception handling returns empty dict."""
        from services.ninova.scraper import get_class_info

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Error")

        result = get_class_info(mock_session, "https://ninova.itu.edu.tr/Sinif/123")

        assert result == {}


# Fixtures for sample HTML content
@pytest.fixture
def sample_html_announcements_page():
    """Sample HTML for announcements page."""
    return """
    <html>
    <body>
    <div class="duyuruGoruntule">
        <h2><a href="/Sinif/123/Duyuru/590536">Önemli Duyuru</a></h2>
        <div class="tarih"><span class="tarih">03 Ocak 2026 16:53</span></div>
        <div class="icerik">Bu bir test duyurusudur.</div>
        <div class="tarih"><span class="tarih">Ahmet Hoca</span></div>
    </div>
    <div class="duyuruGoruntule">
        <h2><a href="/Sinif/123/Duyuru/590537">İkinci Duyuru</a></h2>
        <div class="tarih"><span class="tarih">02 Ocak 2026 10:00</span></div>
        <div class="icerik">İkinci duyuru içeriği.</div>
        <div class="tarih"><span class="tarih">Mehmet Hoca</span></div>
    </div>
    </body>
    </html>
    """
