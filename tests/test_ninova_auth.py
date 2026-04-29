import pytest

from services.ninova.auth import LoginFailedError, login_to_ninova


class _DummyResponse:
    def __init__(self, text="", url="", status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code


class _DummySession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        if url.endswith("/Kampus"):
            return _DummyResponse(status_code=302, url=url)
        if url.endswith("/Login.aspx"):
            return _DummyResponse(
                text='<input name="__VIEWSTATE" value="x" />',
                url=url,
                status_code=200,
            )
        raise AssertionError(f"Unexpected GET url: {url}")

    def post(self, url, data=None, **kwargs):
        self.calls.append(("post", url, data, kwargs))
        return _DummyResponse(text="Hatalı", url="https://ninova.itu.edu.tr/Login.aspx")


def test_invalid_credentials_are_preserved(monkeypatch):
    monkeypatch.setattr("services.ninova.auth.MAX_LOGIN_RETRIES", 1)

    session = _DummySession()

    with pytest.raises(LoginFailedError) as exc_info:
        login_to_ninova(session, "12345", "demo_user", "demo_pass")

    assert exc_info.value.error_type == "INVALID_CREDENTIALS"
    assert exc_info.value.message == "Ninova kullanıcı adı veya şifresi yanlış"
