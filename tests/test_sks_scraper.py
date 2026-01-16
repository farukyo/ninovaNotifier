"""
Tests for services/sks/scraper.py module.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetMealMenu:
    """Tests for get_meal_menu function."""

    @patch("services.sks.scraper.requests.get")
    def test_returns_lunch_menu(self, mock_get):
        """Test returns formatted lunch menu."""
        from services.sks.scraper import get_meal_menu

        html = """
        <table>
            <tr>
                <td>Ana Yemek</td>
                <td><a class="js-nyro-modal">Tavuk Sote</a></td>
            </tr>
            <tr>
                <td>Çorba</td>
                <td><a>Mercimek Çorbası</a></td>
            </tr>
        </table>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_meal_menu("lunch")

        assert result is not None
        assert "Öğle Yemeği" in result
        assert "Tavuk Sote" in result

    @patch("services.sks.scraper.requests.get")
    def test_returns_dinner_menu(self, mock_get):
        """Test returns formatted dinner menu."""
        from services.sks.scraper import get_meal_menu

        html = """
        <table>
            <tr>
                <td>Ana Yemek</td>
                <td><a>Köfte</a></td>
            </tr>
        </table>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_meal_menu("dinner")

        assert result is not None
        assert "Akşam Yemeği" in result

    @patch("services.sks.scraper.requests.get")
    def test_returns_none_on_no_table(self, mock_get):
        """Test returns None when no table found."""
        from services.sks.scraper import get_meal_menu

        mock_response = MagicMock()
        mock_response.text = "<html><body>No table</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_meal_menu("lunch")

        assert result is None

    @patch("services.sks.scraper.requests.get")
    def test_returns_none_on_empty_menu(self, mock_get):
        """Test returns None when menu is empty."""
        from services.sks.scraper import get_meal_menu

        html = """<table><tr><th>Header</th></tr></table>"""

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_meal_menu("lunch")

        assert result is None

    @patch("services.sks.scraper.requests.get")
    def test_returns_none_on_exception(self, mock_get):
        """Test returns None on network error."""
        from services.sks.scraper import get_meal_menu

        mock_get.side_effect = Exception("Network error")

        result = get_meal_menu("lunch")

        assert result is None

    @patch("services.sks.scraper.requests.get")
    def test_filters_out_kalori_rows(self, mock_get):
        """Test that Kalori rows are filtered out."""
        from services.sks.scraper import get_meal_menu

        html = """
        <table>
            <tr>
                <td>Ana Yemek</td>
                <td><a>Tavuk</a></td>
            </tr>
            <tr>
                <td>Kalori</td>
                <td>500</td>
            </tr>
        </table>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_meal_menu("lunch")

        assert result is not None
        assert "Kalori" not in result
