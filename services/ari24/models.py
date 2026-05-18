"""Domain model dataclasses for Ari24 events and news.

Stub — will be populated in Step 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class ClubEvent:
    title: str
    organizer: str
    date_str: str
    link: str
    image_url: str = ""
    date_dt: datetime | None = None


@dataclass
class NewsArticle:
    title: str
    link: str
    image_url: str = ""
