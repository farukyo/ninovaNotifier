"""Helpers for safe Telegram callback_data parsing."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def split_callback_data(data: str, *, sep: str = "_", maxsplit: int = -1) -> list[str]:
    """Split callback data defensively.

    Returns an empty list for empty payloads to simplify guards.
    """
    if not data:
        return []
    if maxsplit >= 0:
        return data.split(sep, maxsplit)
    return data.split(sep)


def parse_int_part(parts: list[str], index: int) -> int | None:
    """Parse integer from split callback parts, return None if invalid."""
    if index >= len(parts):
        return None
    try:
        return int(parts[index])
    except (TypeError, ValueError):
        return None


def url_token(url: str) -> str:
    """URL için kısa ve kararlı bir kimlik (callback_data'ya sığacak 10 hex karakter)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def find_course_file(
    user_grades: dict, urls: list, course_idx: int, file_idx: int, token: str | None
) -> dict | None:
    """
    İndirme butonundaki dosyayı bulur.

    Butonlar ders/dosya sırasını (indeks) taşıyor; derse yeni dosya eklenince veya ders
    silinince sıra kayıyor ve eski bir bildirimdeki buton *başka* bir dosyayı
    indiriyordu. Yeni butonlar dosya URL'inin token'ını da taşır: indeks eşleşmezse
    token ile tüm derslerde aranır. Token'sız eski butonlar indeksle çalışmaya devam eder.
    """
    if 0 <= course_idx < len(urls):
        files = user_grades.get(urls[course_idx], {}).get("files", [])
        if 0 <= file_idx < len(files):
            candidate = files[file_idx]
            if token is None or url_token(candidate.get("url", "")) == token:
                return candidate
    if token:
        for course in user_grades.values():
            for file_data in course.get("files", []):
                if url_token(file_data.get("url", "")) == token:
                    return file_data
    return None


def find_assignment_source_file(
    user_grades: dict,
    urls: list,
    course_idx: int,
    assign_idx: int,
    file_idx: int,
    token: str | None,
) -> dict | None:
    """Ödev kaynak dosyası için find_course_file ile aynı mantık."""
    if 0 <= course_idx < len(urls):
        assignments = user_grades.get(urls[course_idx], {}).get("assignments", [])
        if 0 <= assign_idx < len(assignments):
            source_files = assignments[assign_idx].get("source_files", [])
            if 0 <= file_idx < len(source_files):
                candidate = source_files[file_idx]
                if token is None or url_token(candidate.get("url", "")) == token:
                    return candidate
    if token:
        for course in user_grades.values():
            for assignment in course.get("assignments", []):
                for file_data in assignment.get("source_files", []):
                    if url_token(file_data.get("url", "")) == token:
                        return file_data
    return None


def callback_parse_fail(answer_callback: Callable[[str], None], message: str) -> None:
    """Send a consistent callback parse error response."""
    answer_callback(message)
