"""
Tests for services/ari24/client.py module.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAri24ClientInit:
    """Tests for Ari24Client initialization."""

    def test_headers_are_set(self):
        """Test that User-Agent header is set."""
        from services.ari24.client import Ari24Client

        client = Ari24Client()

        assert "User-Agent" in client.headers
        assert "Mozilla" in client.headers["User-Agent"]


class TestAri24ClientGetEvents:
    """Tests for get_events method."""

    @patch("services.ari24.client.requests.get")
    def test_parses_events_correctly(self, mock_get):
        """Test parsing events from HTML."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a class="etkinlik" href="/etkinlik/123">
            <h2>Test Etkinlik</h2>
            <span class="duzenleyen">Test Kulübü</span>
            <span class="gun">15</span>
            <span class="ay">Oca</span>
            <figure style="background-image: url(/uploads/test.jpg)"></figure>
        </a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_events()

        assert len(result) >= 1
        assert result[0]["title"] == "Test Etkinlik"
        assert result[0]["organizer"] == "Test Kulübü"
        assert "link" in result[0]

    @patch("services.ari24.client.requests.get")
    def test_parses_event_with_time_tag(self, mock_get):
        """Test parsing event with time tag instead of day/month spans."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a class="etkinlik" href="/etkinlik/456">
            <h2>Konferans</h2>
            <span class="duzenleyen">IEEE</span>
            <time>02 Ocak 2026 23:59</time>
        </a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_events()

        assert len(result) >= 1
        assert result[0]["date_str"] == "02 Ocak 2026 23:59"

    @patch("services.ari24.client.requests.get")
    def test_returns_empty_on_error(self, mock_get):
        """Test exception handling returns empty list."""
        from services.ari24.client import Ari24Client

        mock_get.side_effect = Exception("Network error")

        client = Ari24Client()
        result = client.get_events()

        assert result == []

    @patch("services.ari24.client.requests.get")
    def test_handles_missing_elements(self, mock_get):
        """Test handling missing HTML elements gracefully."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a class="etkinlik" href="/etkinlik/789">
            <!-- Missing h2, spans, etc -->
        </a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_events()

        # Should still return something, even with defaults
        assert isinstance(result, list)


class TestAri24ClientGetWeeklyEvents:
    """Tests for get_weekly_events method."""

    @patch.object(
        __import__("services.ari24.client", fromlist=["Ari24Client"]).Ari24Client, "get_events"
    )
    def test_filters_events_by_date_range(self, mock_get_events):
        """Test filtering events within weekly range."""
        from services.ari24.client import Ari24Client

        now = datetime.now()

        mock_get_events.return_value = [
            {"title": "Today Event", "date_dt": now, "link": "/1"},
            {"title": "Tomorrow Event", "date_dt": now + timedelta(days=1), "link": "/2"},
            {"title": "Far Future Event", "date_dt": now + timedelta(days=30), "link": "/3"},
        ]

        client = Ari24Client()
        result = client.get_weekly_events()

        # Should include today and tomorrow, not 30 days from now
        assert len(result) >= 2
        titles = [e["title"] for e in result]
        assert "Today Event" in titles
        assert "Tomorrow Event" in titles

    @patch.object(
        __import__("services.ari24.client", fromlist=["Ari24Client"]).Ari24Client, "get_events"
    )
    def test_excludes_past_events(self, mock_get_events):
        """Test that past events are excluded."""
        from services.ari24.client import Ari24Client

        now = datetime.now()

        mock_get_events.return_value = [
            {"title": "Past Event", "date_dt": now - timedelta(days=5), "link": "/1"},
            {"title": "Future Event", "date_dt": now + timedelta(days=3), "link": "/2"},
        ]

        client = Ari24Client()
        result = client.get_weekly_events()

        titles = [e["title"] for e in result]
        assert "Past Event" not in titles


class TestAri24ClientGetUpcomingEvents:
    """Tests for get_upcoming_events method."""

    @patch.object(
        __import__("services.ari24.client", fromlist=["Ari24Client"]).Ari24Client, "get_events"
    )
    def test_returns_all_events(self, mock_get_events):
        """Test returning all events including those without dates."""
        from services.ari24.client import Ari24Client

        now = datetime.now()

        mock_get_events.return_value = [
            {"title": "Event 1", "date_dt": now, "link": "/1"},
            {"title": "Event 2", "date_dt": None, "link": "/2"},
        ]

        client = Ari24Client()
        result = client.get_upcoming_events()

        assert len(result) == 2


class TestAri24ClientGetAllClubs:
    """Tests for get_all_clubs method."""

    @patch.object(
        __import__("services.ari24.client", fromlist=["Ari24Client"]).Ari24Client, "get_events"
    )
    def test_combines_static_and_active_clubs(self, mock_get_events):
        """Test combining static club list with active organizers."""
        from services.ari24.client import Ari24Client

        mock_get_events.return_value = [
            {"title": "Event", "organizer": "Yeni Kulüp", "link": "/1"},
        ]

        client = Ari24Client()
        result = client.get_all_clubs()

        # Should contain both static clubs and the new one
        assert "Yeni Kulüp" in result
        assert "IEEE İTÜ Öğrenci Kolu" in result  # From static list
        assert len(result) > len(Ari24Client.STATIC_CLUBS)  # Has extra club


class TestAri24ClientGetNews:
    """Tests for get_news method."""

    @patch("services.ari24.client.requests.get")
    def test_parses_news_correctly(self, mock_get):
        """Test parsing news from HTML."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a href="/haber/123">
            <h2>Test Haber</h2>
            <figure style="background-image: url(/uploads/haber.jpg)"></figure>
        </a>
        <a href="/haber/124">
            <h2>İkinci Haber</h2>
        </a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_news(limit=5)

        assert len(result) >= 2
        assert result[0]["title"] == "Test Haber"
        assert "link" in result[0]

    @patch("services.ari24.client.requests.get")
    def test_respects_limit(self, mock_get):
        """Test that limit parameter is respected."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a href="/haber/1"><h2>Haber 1</h2></a>
        <a href="/haber/2"><h2>Haber 2</h2></a>
        <a href="/haber/3"><h2>Haber 3</h2></a>
        <a href="/haber/4"><h2>Haber 4</h2></a>
        <a href="/haber/5"><h2>Haber 5</h2></a>
        <a href="/haber/6"><h2>Haber 6</h2></a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_news(limit=3)

        assert len(result) <= 3

    @patch("services.ari24.client.requests.get")
    def test_returns_empty_on_error(self, mock_get):
        """Test exception handling returns empty list."""
        from services.ari24.client import Ari24Client

        mock_get.side_effect = Exception("Network error")

        client = Ari24Client()
        result = client.get_news()

        assert result == []

    @patch("services.ari24.client.requests.get")
    def test_skips_duplicate_links(self, mock_get):
        """Test that duplicate links are skipped."""
        from services.ari24.client import Ari24Client

        html = """
        <html>
        <body>
        <a href="/haber/123"><h2>Haber</h2></a>
        <a href="/haber/123"><h2>Aynı Haber</h2></a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = Ari24Client()
        result = client.get_news()

        assert len(result) == 1
