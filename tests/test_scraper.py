"""
Tests for services/ninova/scraper.py module.
"""
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetAnnouncements:
    """Tests for get_announcements function."""
    
    def test_parse_announcements_from_html(self, mock_session, sample_html_announcements):
        """Test parsing announcements from HTML."""
        mock_session.get.return_value.text = sample_html_announcements
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_announcements
        
        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        # Should return list of announcements
        assert isinstance(result, list)
    
    def test_empty_announcements_page(self, mock_session):
        """Test when no announcements exist."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_announcements
        
        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_handles_request_exception(self, mock_session):
        """Test handling request exceptions."""
        mock_session.get.side_effect = Exception("Network error")
        
        from services.ninova.scraper import get_announcements
        
        result = get_announcements(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)
        assert len(result) == 0


class TestGetAnnouncementDetail:
    """Tests for get_announcement_detail function."""
    
    def test_get_detail_content(self, mock_session):
        """Test getting announcement detail content."""
        detail_html = """
        <div class="duyuruGoruntule">
            <div class="icerik">Detailed announcement content here.</div>
        </div>
        """
        mock_session.get.return_value.text = detail_html
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_announcement_detail
        
        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")
        
        assert isinstance(result, str)
    
    def test_empty_detail_page(self, mock_session):
        """Test when detail page has no content."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_announcement_detail
        
        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")
        
        assert result == ""
    
    def test_handles_exception(self, mock_session):
        """Test handling exceptions."""
        mock_session.get.side_effect = Exception("Error")
        
        from services.ninova.scraper import get_announcement_detail
        
        result = get_announcement_detail(mock_session, "https://ninova.itu.edu.tr/Duyuru/123")
        
        assert result == ""


class TestGetAssignments:
    """Tests for get_assignments function."""
    
    def test_parse_assignments_from_html(self, mock_session, sample_html_assignments):
        """Test parsing assignments from HTML."""
        mock_session.get.return_value.text = sample_html_assignments
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_assignments
        
        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)
    
    def test_empty_assignments_page(self, mock_session):
        """Test when no assignments exist."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_assignments
        
        result = get_assignments(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)


class TestGetClassFiles:
    """Tests for get_class_files function."""
    
    def test_parse_files_from_html(self, mock_session, sample_html_files):
        """Test parsing files from HTML."""
        mock_session.get.return_value.text = sample_html_files
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_class_files
        
        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)
    
    def test_empty_files_page(self, mock_session):
        """Test when no files exist."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_class_files
        
        result = get_class_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)


class TestGetAllFiles:
    """Tests for get_all_files function."""
    
    def test_combines_class_and_course_files(self, mock_session, sample_html_files):
        """Test that function combines both file types."""
        mock_session.get.return_value.text = sample_html_files
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_all_files
        
        result = get_all_files(mock_session, "https://ninova.itu.edu.tr/Sinif/123")
        
        assert isinstance(result, list)


class TestGetUserCourses:
    """Tests for get_user_courses function."""
    
    def test_parse_courses_from_html(self, mock_session, sample_html_courses):
        """Test parsing user courses from HTML."""
        mock_session.get.return_value.text = sample_html_courses
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_user_courses
        
        result = get_user_courses(mock_session)
        
        assert isinstance(result, list)
    
    def test_empty_courses_page(self, mock_session):
        """Test when user has no courses."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_user_courses
        
        result = get_user_courses(mock_session)
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_handles_exception(self, mock_session):
        """Test handling exceptions."""
        mock_session.get.side_effect = Exception("Error")
        
        from services.ninova.scraper import get_user_courses
        
        result = get_user_courses(mock_session)
        
        assert isinstance(result, list)


class TestGetGrades:
    """Tests for get_grades function."""
    
    def test_parse_grades_from_html(self, mock_session, sample_html_grades):
        """Test parsing grades from HTML."""
        mock_session.get.return_value.text = sample_html_grades
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_grades
        
        # Mock login function
        with patch('services.ninova.scraper.login_to_ninova', return_value=True):
            result = get_grades(
                mock_session, 
                "https://ninova.itu.edu.tr/Sinif/123",
                "12345",
                "username",
                "password"
            )
        
        # get_grades returns a dict with course data
        assert isinstance(result, dict)
        assert "course_name" in result
        assert "grades" in result
    
    def test_empty_grades_page(self, mock_session):
        """Test when no grades exist."""
        mock_session.get.return_value.text = "<html><body></body></html>"
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_grades
        
        with patch('services.ninova.scraper.login_to_ninova', return_value=True):
            result = get_grades(
                mock_session, 
                "https://ninova.itu.edu.tr/Sinif/123",
                "12345",
                "username",
                "password"
            )
        
        # get_grades returns a dict even when empty
        assert isinstance(result, dict)


class TestGetAssignmentDetail:
    """Tests for get_assignment_detail function."""
    
    def test_parse_assignment_dates(self, mock_session):
        """Test parsing assignment detail dates."""
        detail_html = """
        <div id="ctl00_ContentPlaceHolder1_lbBaslangic">26 Aralık 2025 00:00</div>
        <div id="ctl00_ContentPlaceHolder1_lbBitis">06 Ocak 2026 23:30</div>
        <a href="OdevGonder">Ödevi Yükle</a>
        """
        mock_session.get.return_value.text = detail_html
        mock_session.get.return_value.status_code = 200
        
        from services.ninova.scraper import get_assignment_detail
        
        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")
        
        assert isinstance(result, dict)
    
    def test_handles_exception(self, mock_session):
        """Test handling exceptions."""
        mock_session.get.side_effect = Exception("Error")
        
        from services.ninova.scraper import get_assignment_detail
        
        result = get_assignment_detail(mock_session, "https://ninova.itu.edu.tr/Odev/123")
        
        # get_assignment_detail returns None on exception
        assert result is None
