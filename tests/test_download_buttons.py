"""Download buttons must resolve the same file even after the file list changes."""

from bot.callback_parsing import find_assignment_source_file, find_course_file, url_token

COURSE_A = "https://ninova.itu.edu.tr/Sinif/1"
COURSE_B = "https://ninova.itu.edu.tr/Sinif/2"


def _grades(files_a, files_b=()):
    return {
        COURSE_A: {"files": list(files_a), "assignments": []},
        COURSE_B: {"files": list(files_b), "assignments": []},
    }


def _file(name):
    return {"name": name, "url": f"https://f/{name}"}


def test_index_match_with_token():
    grades = _grades([_file("a"), _file("b")])
    found = find_course_file(grades, list(grades), 0, 1, url_token("https://f/b"))
    assert found["name"] == "b"


def test_shifted_list_is_resolved_by_token():
    # Regresyon: bildirim gönderildikten sonra listenin başına dosya eklenince eski
    # buton (dl_0_0) başka bir dosyayı indiriyordu.
    token = url_token("https://f/a")
    grades = _grades([_file("new"), _file("a")])
    assert find_course_file(grades, list(grades), 0, 0, token)["name"] == "a"


def test_deleted_course_shift_is_resolved_by_token():
    token = url_token("https://f/x")
    grades = {COURSE_B: {"files": [_file("x")]}}
    assert find_course_file(grades, list(grades), 1, 0, token)["name"] == "x"


def test_legacy_button_without_token_uses_index():
    grades = _grades([_file("a"), _file("b")])
    assert find_course_file(grades, list(grades), 0, 1, None)["name"] == "b"


def test_missing_file_returns_none():
    grades = _grades([_file("a")])
    assert find_course_file(grades, list(grades), 0, 0, url_token("https://f/gone")) is None
    assert find_course_file(grades, list(grades), 5, -1, None) is None


def test_assignment_source_file_resolved_by_token():
    token = url_token("https://f/src")
    grades = {
        COURSE_A: {
            "assignments": [
                {"source_files": [_file("other")]},
                {"source_files": [_file("src")]},
            ]
        }
    }
    assert find_assignment_source_file(grades, list(grades), 0, 0, 0, token)["name"] == "src"
    assert find_assignment_source_file(grades, list(grades), 0, 1, 0, None)["name"] == "src"
