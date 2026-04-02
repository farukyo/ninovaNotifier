"""Tests for Ninova file source aggregation behavior."""

from services.ninova import scraper


def test_get_all_files_combines_both_sources(monkeypatch):
    """Both endpoints should be merged into a single list with source labels."""

    def fake_get_class_files(_session, _base_url, file_type="SinifDosyalari", **_kwargs):
        if file_type == "SinifDosyalari":
            return [{"name": "a.pdf", "url": "u1", "date": "d1", "size": "1 MB"}]
        return [{"name": "b.pdf", "url": "u2", "date": "d2", "size": "2 MB"}]

    monkeypatch.setattr(scraper, "get_class_files", fake_get_class_files)

    files = scraper.get_all_files(session=object(), base_url="https://ninova.itu.edu.tr/Sinif/1")

    assert files is not None
    assert len(files) == 2
    assert {f["source"] for f in files} == {"Sınıf", "Ders"}


def test_get_all_files_keeps_available_source_when_other_fails(monkeypatch):
    """If one endpoint fails, available files should still be returned."""

    def fake_get_class_files(_session, _base_url, file_type="SinifDosyalari", **_kwargs):
        if file_type == "SinifDosyalari":
            return [{"name": "a.pdf", "url": "u1", "date": "d1", "size": "1 MB"}]
        return None

    monkeypatch.setattr(scraper, "get_class_files", fake_get_class_files)

    files = scraper.get_all_files(session=object(), base_url="https://ninova.itu.edu.tr/Sinif/1")

    assert files is not None
    assert len(files) == 1
    assert files[0]["source"] == "Sınıf"


def test_get_all_files_returns_none_if_both_fail(monkeypatch):
    """If both endpoints fail, caller should mark fetch as failed."""

    def fake_get_class_files(_session, _base_url, **_kwargs):
        return None

    monkeypatch.setattr(scraper, "get_class_files", fake_get_class_files)

    files = scraper.get_all_files(session=object(), base_url="https://ninova.itu.edu.tr/Sinif/1")

    assert files is None
