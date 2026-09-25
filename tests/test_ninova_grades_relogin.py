"""get_grades should re-login when Ninova serves the login form with HTTP 200."""

from services.ninova import scraper

LOGIN_HTML = '<input name="ctl00$ContentPlaceHolder1$tbUserName" />'
GRADES_HTML = """
<table class="data">
  <tr><th>Değerlendirme</th><th>Not</th></tr>
  <tr><td>Vize</td><td>90</td></tr>
</table>
"""


class _Resp:
    def __init__(self, text, url, status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code


def test_get_grades_relogins_on_login_page(monkeypatch):
    base = "https://ninova.itu.edu.tr/Sinif/1"
    pages = iter([LOGIN_HTML, GRADES_HTML])
    logins = []

    monkeypatch.setattr(
        scraper,
        "http_request",
        lambda _log, _session, _method, url, **_kw: _Resp(next(pages), url),
    )
    monkeypatch.setattr(
        scraper, "login_to_ninova", lambda *args, **_kwargs: logins.append(args) or True
    )
    monkeypatch.setattr(scraper, "get_assignments", lambda *_a: None)
    monkeypatch.setattr(scraper, "get_all_files", lambda *_a: [])
    monkeypatch.setattr(scraper, "get_announcements", lambda *_a: [])

    data = scraper.get_grades(object(), base, "1", "user", "pw")

    assert len(logins) == 1
    assert data["grades"]["Vize"]["not"] == "90"
    assert data["failed_sections"] == ["assignments"]
    assert data["fetch_success"] is False
