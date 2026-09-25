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


class _FakeNinovaSession:
    """Oturumu düşmüş bir Ninova: giriş yapılana kadar her sayfa 200 ile login formu döner."""

    def __init__(self):
        self.logged_in = False
        self.posts = 0

    def request(self, method, url, **_kwargs):
        if method == "POST":
            self.posts += 1
            self.logged_in = True
            return _Resp("<html>Kampus</html>", "https://ninova.itu.edu.tr/Kampus1")
        if url.endswith("/Login.aspx"):
            return _Resp(LOGIN_HTML, url)
        if not self.logged_in:
            return _Resp(LOGIN_HTML, url)
        if url.endswith("/Notlar"):
            return _Resp(GRADES_HTML, url)
        return _Resp("<html></html>", url)


def test_get_grades_relogins_through_real_auth_path(monkeypatch):
    # Regresyon: login_to_ninova /Kampus'tan gelen her 200'ü "oturum açık" sayıyordu;
    # login formu 200 ile döndüğünde hiç giriş yapılmıyor ve SESSION_ERROR oluşuyordu.
    monkeypatch.setattr(scraper, "get_assignments", lambda *_a: [])
    monkeypatch.setattr(scraper, "get_all_files", lambda *_a: [])
    monkeypatch.setattr(scraper, "get_announcements", lambda *_a: [])
    session = _FakeNinovaSession()

    data = scraper.get_grades(session, "https://ninova.itu.edu.tr/Sinif/1", "1", "u", "p")

    assert session.posts == 1
    assert data["grades"]["Vize"]["not"] == "90"
