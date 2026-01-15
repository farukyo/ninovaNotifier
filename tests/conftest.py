"""
Pytest configuration and shared fixtures for ninovaNotifier tests.
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_users_file(temp_dir):
    """Create a mock users.json file."""
    users_file = os.path.join(temp_dir, "users.json")
    users_data = {
        "12345": {
            "username": "testuser",
            "password": "encrypted_password_here",
            "urls": ["/Sinif/2123.110928"],
        },
        "67890": {
            "username": "anotheruser",
            "password": "another_encrypted",
            "urls": [],
        },
    }
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users_data, f)
    return users_file


@pytest.fixture
def mock_data_file(temp_dir):
    """Create a mock ninova_data.json file."""
    data_file = os.path.join(temp_dir, "ninova_data.json")
    grades_data = {
        "12345": {
            "/Sinif/2123.110928": {
                "course_name": "Test Course",
                "grades": [{"name": "Midterm", "grade": "85", "weight": "30%"}],
                "files": [{"name": "lectures/week1.pdf", "url": "/download/1"}],
            }
        }
    }
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(grades_data, f)
    return data_file


@pytest.fixture
def mock_cache_file(temp_dir):
    """Create a mock file_cache.json file."""
    cache_file = os.path.join(temp_dir, "file_cache.json")
    cache_data = {"https://ninova.itu.edu.tr/file1": "file_id_abc123"}
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)
    return cache_file


@pytest.fixture
def mock_session():
    """Create a mock requests.Session."""
    return MagicMock()


@pytest.fixture
def mock_telegram_response():
    """Create a mock successful Telegram API response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "ok": True,
        "result": {"document": {"file_id": "test_file_id_12345"}},
    }
    return response


@pytest.fixture
def sample_html_announcements():
    """Sample HTML response for announcements page."""
    return """
    <div class="duyrular">
        <div class="duyuru">
            <h2><a href="/Duyuru/123">Önemli Duyuru</a></h2>
            <div class="icerik">Bu bir test duyurusudur...</div>
            <div class="tarih"><span class="tarih">Ahmet Hoca</span></div>
        </div>
        <div class="duyuru">
            <h2><a href="/Duyuru/124">İkinci Duyuru</a></h2>
            <div class="icerik">İkinci duyuru içeriği...</div>
            <div class="tarih"><span class="tarih">Mehmet Hoca</span></div>
        </div>
    </div>
    """


@pytest.fixture
def sample_html_grades():
    """Sample HTML response for grades page."""
    return """
    <table class="data">
        <tr>
            <th>Değerlendirme</th>
            <th>Not</th>
            <th>Ağırlık</th>
            <th>Ortalama</th>
            <th>Std.Sapma</th>
        </tr>
        <tr>
            <td>Vize 1</td>
            <td>85</td>
            <td>%30</td>
            <td>72.5</td>
            <td>12.3</td>
        </tr>
        <tr>
            <td>Final</td>
            <td>90</td>
            <td>%50</td>
            <td>68.2</td>
            <td>15.1</td>
        </tr>
    </table>
    """


@pytest.fixture
def sample_html_assignments():
    """Sample HTML response for assignments page."""
    return """
    <table class="data">
        <tr>
            <td>
                <h2><a href="/Sinif/xxx/Odev/241922">STM Experiment 4</a></h2>
                <strong>Teslim Başlangıcı : </strong>26 Aralık 2025 00:00<br />
                <strong>Teslim Bitişi : </strong>06 Ocak 2026 23:30<br />
                Ödevde istenen toplam <strong class="uyari">1</strong> adet dosyanın
                <strong class="uyari">1</strong> adedini sisteme yüklediniz.
            </td>
        </tr>
        <tr>
            <td>
                <h2><a href="/Sinif/xxx/Odev/241923">Lab Report 5</a></h2>
                <strong>Teslim Başlangıcı : </strong>01 Ocak 2026 00:00<br />
                <strong>Teslim Bitişi : </strong>15 Ocak 2026 23:59<br />
            </td>
        </tr>
    </table>
    """


@pytest.fixture
def sample_html_files():
    """Sample HTML response for class files page."""
    return """
    <table class="data">
        <tr>
            <td><img src='/images/ds/folder.png' /><a href="?g8223370">Lectures</a></td>
            <td>6 MB</td>
            <td>23 Aralık 2025 08:20</td>
        </tr>
        <tr>
            <td><img src='/images/ds/pdf.png' /><a href="/Dosyalar/234234234">Syllabus.pdf</a></td>
            <td>1 MB</td>
            <td>15 Eylül 2025 14:30</td>
        </tr>
    </table>
    """


@pytest.fixture
def sample_html_courses():
    """Sample HTML response for user courses page."""
    return """
    <div class="menuErisimAgaci">
        <ul>
            <li>
                <span><strong>BLG 212E</strong></span>
                <ul>
                    <li>
                        <a href="/Sinif/2123.110928"><span>Microprocessor Systems</span></a>
                    </li>
                </ul>
            </li>
            <li>
                <span><strong>EHB 231E</strong></span>
                <ul>
                    <li>
                        <a href="/Sinif/2123.110929"><span>Digital Circuits</span></a>
                    </li>
                </ul>
            </li>
        </ul>
    </div>
    """
