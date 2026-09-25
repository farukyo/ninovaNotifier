"""get_assignments should only fetch assignment detail pages when needed."""

import time

import pytest

from services.ninova import scraper

BASE = "https://ninova.itu.edu.tr/Sinif/1"
LIST_HTML = """
<table id="ctl00_ContentPlaceHolder1_gvOdevListesi">
  <tr><th>Ödev</th></tr>
  <tr><td>
    <h2><a href="/Sinif/1/Odev/77">HW1</a></h2>
    <strong>Teslim Başlangıcı : </strong>01 Ocak 2099 00:00<br />
    <strong>Teslim Bitişi : </strong>10 Ocak 2099 23:59<br />
    Ödevde istenen toplam <strong class="uyari">1</strong> adet dosyanın
    <strong class="uyari">0</strong> adedini sisteme yüklediniz.
  </td></tr>
</table>
"""


class _Resp:
    status_code = 200

    def __init__(self, url):
        self.text = LIST_HTML
        self.url = url


@pytest.fixture
def detail_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(scraper, "http_request", lambda _l, _s, _m, url, **_k: _Resp(url))

    def fake_detail(_session, url):
        calls.append(url)
        return {
            "start_date": "01 Ocak 2099 00:00",
            "end_date": "10 Ocak 2099 23:59",
            "is_submitted": False,
            "description": "desc",
            "source_files": [{"name": "a.pdf", "url": "u", "size": "1", "date": "d"}],
            "required_files": [],
        }

    monkeypatch.setattr(scraper, "get_assignment_detail", fake_detail)
    return calls


def test_first_fetch_loads_detail(detail_calls):
    result = scraper.get_assignments(object(), BASE)
    assert len(detail_calls) == 1
    assert result[0]["source_files"][0]["name"] == "a.pdf"
    assert "detail_fetched_at" in result[0]


def test_unchanged_fresh_assignment_reuses_saved_detail(detail_calls):
    first = scraper.get_assignments(object(), BASE)
    detail_calls.clear()

    second = scraper.get_assignments(object(), BASE, first)

    assert detail_calls == []
    assert second[0]["source_files"] == first[0]["source_files"]
    assert second[0]["description"] == "desc"


def test_stale_detail_is_refreshed(detail_calls):
    first = scraper.get_assignments(object(), BASE)
    first[0]["detail_fetched_at"] = time.time() - scraper.ASSIGNMENT_DETAIL_REFRESH_ACTIVE - 1
    detail_calls.clear()

    scraper.get_assignments(object(), BASE, first)

    assert len(detail_calls) == 1


def test_changed_list_row_triggers_refresh(detail_calls):
    first = scraper.get_assignments(object(), BASE)
    first[0]["list_signature"] = "something else"
    detail_calls.clear()

    scraper.get_assignments(object(), BASE, first)

    assert len(detail_calls) == 1


def test_saved_data_without_detail_timestamp_is_refreshed(detail_calls):
    first = scraper.get_assignments(object(), BASE)
    del first[0]["detail_fetched_at"]  # eski formatta kaydedilmiş veri
    detail_calls.clear()

    scraper.get_assignments(object(), BASE, first)

    assert len(detail_calls) == 1
