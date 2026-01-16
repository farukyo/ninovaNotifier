"""
Tests for services/calendar/itu_calendar.py module.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCalendarEvent:
    """Tests for CalendarEvent dataclass."""

    def test_create_calendar_event(self):
        """Test creating a CalendarEvent instance."""
        from services.calendar.itu_calendar import CalendarEvent

        event = CalendarEvent(
            name="Ders Başlangıcı",
            date_str="06 Ocak 2026",
            status="3 gün kaldı",
            is_past=False,
        )

        assert event.name == "Ders Başlangıcı"
        assert event.date_str == "06 Ocak 2026"
        assert event.status == "3 gün kaldı"
        assert event.is_past is False

    def test_create_past_event(self):
        """Test creating a past CalendarEvent."""
        from services.calendar.itu_calendar import CalendarEvent

        event = CalendarEvent(
            name="Kayıt Bitiş",
            date_str="01 Aralık 2025",
            status="Geçti",
            is_past=True,
        )

        assert event.is_past is True


class TestCalendarSection:
    """Tests for CalendarSection dataclass."""

    def test_create_calendar_section(self):
        """Test creating a CalendarSection instance."""
        from services.calendar.itu_calendar import CalendarEvent, CalendarSection

        events = [
            CalendarEvent("Event 1", "01 Ocak 2026", "5 gün kaldı", False),
            CalendarEvent("Event 2", "10 Ocak 2026", "14 gün kaldı", False),
        ]

        section = CalendarSection(title="Güz Dönemi 2025-2026", events=events)

        assert section.title == "Güz Dönemi 2025-2026"
        assert len(section.events) == 2


class TestITUCalendarServiceFetchCalendar:
    """Tests for ITUCalendarService.fetch_calendar method."""

    @patch("services.calendar.itu_calendar.requests.get")
    def test_parses_calendar_correctly(self, mock_get):
        """Test parsing calendar from HTML."""
        from services.calendar.itu_calendar import ITUCalendarService

        html = """
        <html>
        <body>
        <table class="table table-bordered table-striped table-hover">
            <tr>
                <td class="tablo-baslik">Lisans / Önlisans Akademik Takvimi</td>
            </tr>
            <tr>
                <td>Ders Kayıtları</td>
                <td>06 Ocak 2026</td>
                <td>3 gün kaldı</td>
            </tr>
            <tr>
                <td>Derslerin Başlangıcı</td>
                <td>13 Ocak 2026</td>
                <td>10 gün kaldı</td>
            </tr>
        </table>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = ITUCalendarService.fetch_calendar()

        assert len(result) >= 1
        assert result[0].title == "Lisans / Önlisans Akademik Takvimi"
        assert len(result[0].events) >= 2

    @patch("services.calendar.itu_calendar.requests.get")
    def test_returns_empty_on_no_table(self, mock_get):
        """Test returns empty list when no table found."""
        from services.calendar.itu_calendar import ITUCalendarService

        html = "<html><body>No table here</body></html>"

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = ITUCalendarService.fetch_calendar()

        assert result == []

    @patch("services.calendar.itu_calendar.requests.get")
    def test_returns_empty_on_error(self, mock_get):
        """Test returns empty list on exception."""
        from services.calendar.itu_calendar import ITUCalendarService

        mock_get.side_effect = Exception("Network error")

        result = ITUCalendarService.fetch_calendar()

        assert result == []

    @patch("services.calendar.itu_calendar.requests.get")
    def test_identifies_past_events(self, mock_get):
        """Test correctly identifying past events."""
        from services.calendar.itu_calendar import ITUCalendarService

        html = """
        <html>
        <body>
        <table class="table table-bordered table-striped table-hover">
            <tr>
                <td class="tablo-baslik">Güz Dönemi</td>
            </tr>
            <tr>
                <td>Eski Etkinlik</td>
                <td>01 Eylül 2025</td>
                <td>Geçti</td>
            </tr>
        </table>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = ITUCalendarService.fetch_calendar()

        assert len(result) >= 1
        assert result[0].events[0].is_past is True

    @patch("services.calendar.itu_calendar.requests.get")
    def test_handles_multiple_sections(self, mock_get):
        """Test parsing multiple calendar sections."""
        from services.calendar.itu_calendar import ITUCalendarService

        html = """
        <html>
        <body>
        <table class="table table-bordered table-striped table-hover">
            <tr>
                <td class="tablo-baslik">Güz Dönemi</td>
            </tr>
            <tr>
                <td>Etkinlik 1</td>
                <td>01 Ocak 2026</td>
                <td>5 gün kaldı</td>
            </tr>
            <tr>
                <td class="tablo-baslik">Bahar Dönemi</td>
            </tr>
            <tr>
                <td>Etkinlik 2</td>
                <td>01 Şubat 2026</td>
                <td>35 gün kaldı</td>
            </tr>
        </table>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = ITUCalendarService.fetch_calendar()

        assert len(result) == 2
        assert result[0].title == "Güz Dönemi"
        assert result[1].title == "Bahar Dönemi"


class TestITUCalendarServiceGetFilteredCalendar:
    """Tests for ITUCalendarService.get_filtered_calendar method."""

    @patch.object(
        __import__(
            "services.calendar.itu_calendar", fromlist=["ITUCalendarService"]
        ).ITUCalendarService,
        "fetch_calendar",
    )
    def test_returns_error_on_empty_calendar(self, mock_fetch):
        """Test returns error message when calendar is empty."""
        from services.calendar.itu_calendar import ITUCalendarService

        mock_fetch.return_value = []

        result = ITUCalendarService.get_filtered_calendar()

        assert "alınamadı" in result

    @patch.object(
        __import__(
            "services.calendar.itu_calendar", fromlist=["ITUCalendarService"]
        ).ITUCalendarService,
        "fetch_calendar",
    )
    @patch("services.calendar.itu_calendar.parse_turkish_date")
    def test_filters_past_events_by_default(self, mock_parse_date, mock_fetch):
        """Test that past events are hidden by default."""
        from services.calendar.itu_calendar import (
            CalendarEvent,
            CalendarSection,
            ITUCalendarService,
        )

        now = datetime.now()

        # Create events
        past_event = CalendarEvent("Past", "01 Aralık 2025", "Geçti", is_past=True)
        future_event = CalendarEvent("Future", "01 Ocak 2026", "5 gün kaldı", is_past=False)

        mock_fetch.return_value = [
            CalendarSection("Lisans / Önlisans Akademik Takvimi", [past_event, future_event])
        ]
        mock_parse_date.return_value = now + timedelta(days=5)

        result = ITUCalendarService.get_filtered_calendar(show_past=False)

        # Past event should be hidden
        assert "Past" not in result or "gizlendi" in result

    @patch.object(
        __import__(
            "services.calendar.itu_calendar", fromlist=["ITUCalendarService"]
        ).ITUCalendarService,
        "fetch_calendar",
    )
    @patch("services.calendar.itu_calendar.parse_turkish_date")
    def test_shows_all_when_flags_true(self, mock_parse_date, mock_fetch):
        """Test showing all events when show_past and show_future are True."""
        from services.calendar.itu_calendar import (
            CalendarEvent,
            CalendarSection,
            ITUCalendarService,
        )

        now = datetime.now()

        past_event = CalendarEvent("Past Event", "01 Aralık 2025", "Geçti", is_past=True)
        future_event = CalendarEvent("Future Event", "01 Mart 2026", "60 gün kaldı", is_past=False)

        mock_fetch.return_value = [
            CalendarSection("Lisans / Önlisans Akademik Takvimi", [past_event, future_event])
        ]
        mock_parse_date.return_value = now + timedelta(days=60)

        result = ITUCalendarService.get_filtered_calendar(show_past=True, show_future=True)

        assert "Tüm Etkinlikler" in result

    @patch.object(
        __import__(
            "services.calendar.itu_calendar", fromlist=["ITUCalendarService"]
        ).ITUCalendarService,
        "fetch_calendar",
    )
    @patch("services.calendar.itu_calendar.parse_turkish_date")
    def test_displays_ongoing_events(self, mock_parse_date, mock_fetch):
        """Test ongoing events are displayed with correct icon."""
        from services.calendar.itu_calendar import (
            CalendarEvent,
            CalendarSection,
            ITUCalendarService,
        )

        ongoing_event = CalendarEvent(
            "Ders Ekleme", "06-10 Ocak 2026", "Devam ediyor", is_past=False
        )

        mock_fetch.return_value = [
            CalendarSection("Lisans / Önlisans Akademik Takvimi", [ongoing_event])
        ]
        mock_parse_date.return_value = None

        result = ITUCalendarService.get_filtered_calendar()

        assert "🔥" in result or "Devam ediyor" in result
