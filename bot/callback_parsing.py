"""Helpers for safe Telegram callback_data parsing."""

from __future__ import annotations

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


def callback_parse_fail(answer_callback: Callable[[str], None], message: str) -> None:
    """Send a consistent callback parse error response."""
    answer_callback(message)
