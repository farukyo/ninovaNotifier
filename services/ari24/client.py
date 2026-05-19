from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("ninova")

_CLUBS_FILE = Path("data") / "ari24_clubs.json"


def _load_static_clubs() -> list[str]:
    """data/ari24_clubs.json dosyasından kulüp listesini yükler."""
    if _CLUBS_FILE.exists():
        try:
            with _CLUBS_FILE.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


MONTH_MAP = {
    "Oca": 1,
    "Şub": 2,
    "Mar": 3,
    "Nis": 4,
    "May": 5,
    "Haz": 6,
    "Tem": 7,
    "Ağu": 8,
    "Eyl": 9,
    "Eki": 10,
    "Kas": 11,
    "Ara": 12,
    "Ocak": 1,
    "Şubat": 2,
    "Mart": 3,
    "Nisan": 4,
    "Mayıs": 5,
    "Haziran": 6,
    "Temmuz": 7,
    "Ağustos": 8,
    "Eylül": 9,
    "Ekim": 10,
    "Kasım": 11,
    "Aralık": 12,
}


class Ari24Client:
    BASE_URL = "https://ari24.com"
    EVENTS_URL = "https://ari24.com/etkinlikler"
    NEWS_URL = "https://ari24.com/haberler"
    CLUBS_URL = "https://ari24.com/kulupler"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _parse_month(self, month_str: str) -> int | None:
        return MONTH_MAP.get(month_str.strip())

    def _parse_date_from_text(self, text: str) -> tuple[str, datetime | None]:
        match = re.search(r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\b", text)
        if not match:
            return "", None

        day_str, month_str = match.groups()
        month_num = self._parse_month(month_str)
        if not month_num:
            return f"{day_str} {month_str}", None

        now = datetime.now()
        year = now.year
        if month_num < now.month - 2:
            year += 1

        with contextlib.suppress(ValueError):
            return f"{day_str} {month_str}", datetime(year, month_num, int(day_str))

        return f"{day_str} {month_str}", None

    def _extract_image_url(self, tag) -> str:
        img_tag = tag.find("img") if tag else None
        if not img_tag:
            return ""

        for attr in ("src", "data-src"):
            raw_src = img_tag.get(attr)
            if raw_src:
                return self._normalize_image_url(raw_src)

        srcset = img_tag.get("srcset") or ""
        if srcset:
            last_src = srcset.split(",")[-1].strip().split(" ")[0]
            return self._normalize_image_url(last_src)

        return ""

    def _normalize_image_url(self, url: str) -> str:
        if not url:
            return ""

        if url.startswith("/"):
            url = self.BASE_URL + url

        parsed = urlparse(url)
        if parsed.path.endswith("/_next/image"):
            params = parse_qs(parsed.query)
            raw = params.get("url", [""])[0]
            if raw:
                raw = unquote(raw)
                if raw.startswith("/"):
                    return self.BASE_URL + raw
                return raw

        return url

    def get_events(self) -> list[dict]:
        """
        Fetches events from ari24.com/etkinlikler.
        Returns a list of dictionaries with keys:
        - title: Event title
        - organizer: Club/Organizer name
        - date_str: Original date string
        - date_dt: datetime object (if parsable)
        - image_url: URL of the event cover image
        - link: Full URL to the event detail
        """
        try:
            response = requests.get(self.EVENTS_URL, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            events = []
            event_items = soup.find_all("a", href=lambda x: x and "/etkinlik/" in x)

            for item in event_items:
                try:
                    link = item.get("href")
                    if link and not link.startswith("http"):
                        link = self.BASE_URL + link

                    raw_text = " ".join(item.get_text(" ", strip=True).split())
                    raw_text = raw_text.replace("Etkinlik kapağı ", "")

                    date_str, date_dt = self._parse_date_from_text(raw_text)

                    title = "Başlıksız Etkinlik"
                    organizer = "Bilinmiyor"

                    if date_str:
                        parts = raw_text.split(date_str, 1)
                        if parts[0].strip():
                            title = parts[0].strip()
                        if len(parts) > 1 and parts[1].strip():
                            organizer = parts[1].strip()
                    else:
                        title = raw_text or title

                    if not date_dt:
                        time_tag = item.find("time")
                        if time_tag:
                            full_date_text = time_tag.get_text(strip=True)
                            match = re.search(
                                r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})",
                                full_date_text,
                            )
                            if match:
                                day_str, month_str, year_str = match.groups()
                                month_num = self._parse_month(month_str)
                                if month_num:
                                    with contextlib.suppress(ValueError):
                                        date_dt = datetime(int(year_str), month_num, int(day_str))
                            date_str = date_str or full_date_text

                    image_url = self._extract_image_url(item)

                    events.append(
                        {
                            "title": title,
                            "organizer": organizer,
                            "date_str": date_str,
                            "date_dt": date_dt,
                            "image_url": image_url,
                            "link": link,
                        }
                    )

                except Exception as e:
                    logger.debug(f"Skipping event item due to parse error: {e}")  # fix: BUG-E2
                    continue

            return events

        except Exception as e:
            logger.error(f"Error fetching Arı24 events: {e}")  # fix: BUG-E2
            return []

    def get_weekly_events(self) -> list[dict]:
        """Returns events for the current week (Monday to Sunday)."""
        events = self.get_events()
        data = []
        now = datetime.now()
        # Find start of period. User wants upcoming events, so start from TODAY.
        # However, we still want to keep the "Weekly" semantic (end of next week).

        # Start from today, 00:00
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate end of next week (finding next Sunday + 7 days)
        # current logic: start_of_week was Monday. end_of_week was Monday + 13 (Next Sunday).
        # We can keep the end date logic same but change start comparison.

        current_monday = now - timedelta(days=now.weekday())
        current_monday = current_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = current_monday + timedelta(days=13)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        for event in events:
            if event["date_dt"]:
                # Check if event is within range AND in the future/today
                # logic: event must be >= start_date (Today) AND <= end_date (Next Sunday)
                if start_date <= event["date_dt"] <= end_date:
                    data.append(event)
            else:
                # If date parsing failed, maybe include?
                # Better safe than sorry, but might spam. Let's include if unsure.
                pass
        return data

    def get_upcoming_events(self) -> list[dict]:
        """Returns events that represent 'this week' or future."""
        return list(self.get_events())

    def get_all_clubs(self) -> list[str]:
        """Extracts unique list of organizers/clubs from current events + data/ari24_clubs.json."""
        events = self.get_events()
        active_clubs = {ev["organizer"] for ev in events if ev["organizer"]}
        static_clubs = set(_load_static_clubs())
        scraped_clubs = set(self.get_clubs())
        return sorted(static_clubs | active_clubs | scraped_clubs)

    def _fetch_club_page(self, page: int) -> list[str]:
        params = {"page": page} if page > 1 else None
        response = requests.get(self.CLUBS_URL, headers=self.headers, params=params, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        clubs = []
        for tag in soup.select('a[class*="ClubCard"][class*="title"]'):
            name = " ".join(tag.get_text(" ", strip=True).split())
            if name:
                clubs.append(name)

        return clubs

    def get_clubs(self, max_pages: int = 20) -> list[str]:
        """Fetches club names from ari24.com/kulupler across multiple pages."""
        try:
            clubs = []
            seen = set()

            for page in range(1, max_pages + 1):
                page_clubs = self._fetch_club_page(page)
                new_clubs = [name for name in page_clubs if name not in seen]
                if not new_clubs:
                    break
                clubs.extend(new_clubs)
                seen.update(new_clubs)

            return clubs
        except Exception as e:
            logger.error(f"Error fetching Arı24 clubs: {e}")  # fix: BUG-E2
            return []

    def get_news(self, limit: int = 5) -> list[dict]:
        """
        Fetches news articles from ari24.com/haberler.
        Returns a list of dictionaries with keys:
        - title: News title
        - link: Full URL to the news article
        - image_url: URL of the news cover image (if available)
        """
        try:
            response = requests.get(self.NEWS_URL, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            news = []
            # News items are links containing h2 tags
            news_items = soup.find_all("a", href=lambda x: x and "/haber/" in x)

            seen_links = set()
            for item in news_items:
                link = item.get("href", "")
                if not link.startswith("http"):
                    link = self.BASE_URL + link

                # Skip duplicates
                if link in seen_links:
                    continue
                seen_links.add(link)

                # Get title from h2 or text
                title_tag = item.find("h2")
                title = title_tag.get_text(strip=True) if title_tag else item.get_text(strip=True)

                if not title:
                    continue

                image_url = self._extract_image_url(item)

                news.append({"title": title, "link": link, "image_url": image_url})

                if len(news) >= limit:
                    break

            return news
        except Exception as e:
            logger.error(f"Error fetching news: {e}")  # fix: BUG-E2
            return []
