import contextlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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
}


class Ari24Client:
    BASE_URL = "https://ari24.com"
    EVENTS_URL = "https://ari24.com/etkinlikler"
    NEWS_URL = "https://ari24.com/haberler"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def get_events(self):
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
            event_items = soup.find_all("a", class_="etkinlik")

            for item in event_items:
                try:
                    link = item.get("href")
                    if link and not link.startswith("http"):
                        link = self.BASE_URL + link

                    title_tag = item.find("h2")
                    title = title_tag.get_text(strip=True) if title_tag else "Başlıksız Etkinlik"

                    organizer_tag = item.find("span", class_="duzenleyen")
                    organizer = (
                        organizer_tag.get_text(strip=True) if organizer_tag else "Bilinmiyor"
                    )

                    # Parse Date
                    day_tag = item.find("span", class_="gun")
                    month_tag = item.find("span", class_="ay")

                    date_dt = None
                    date_str = ""

                    if day_tag and month_tag:
                        day = day_tag.get_text(strip=True)
                        month_str = month_tag.get_text(strip=True)
                        date_str = f"{day} {month_str}"

                        # Try to construct datetime
                        # Assuming current year if month is future, next year if month passed?
                        # Or just basic parsing. Let's try to assume current year first.
                        now = datetime.now()
                        month_num = MONTH_MAP.get(month_str, 1)
                        try:
                            # A naive assumption about year
                            year = now.year
                            # If month is much earlier than now, maybe it's next year?
                            # But usually these are upcoming.
                            # If month < current month - 2, maybe next year.
                            if month_num < now.month - 2:
                                year += 1

                            date_dt = datetime(year, month_num, int(day))
                        except ValueError:
                            pass
                    else:
                        # Fallback for alternative structure: <time>02 Ocak 2026 23:59</time>
                        time_tag = item.find("time")
                        if time_tag:
                            full_date_text = time_tag.get_text(strip=True)
                            date_str = full_date_text
                            # Try parsing "DD Month YYYY HH:MM"
                            # Regex to capture components
                            # Example: "02 Ocak 2026 23:59"
                            match = re.search(r"(\d+)\s+(\w+)\s+(\d+)", full_date_text)
                            if match:
                                day_str, month_str, year_str = match.groups()
                                month_num = MONTH_MAP.get(month_str, 1)
                                with contextlib.suppress(ValueError):
                                    date_dt = datetime(int(year_str), month_num, int(day_str))

                    # Extract Image
                    # style="background-image: url(/uploads/...)"
                    image_url = ""
                    figure = item.find("figure")
                    if figure and figure.get("style"):
                        style = figure["style"]
                        match = re.search(r"url\((.*?)\)", style)
                        if match:
                            img_path = match.group(1).strip("'\"")
                            if img_path.startswith("/"):
                                image_url = self.BASE_URL + img_path
                            else:
                                image_url = img_path

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
                    print(f"Skipping an event item due to parse error: {e}")
                    continue

            return events

        except Exception as e:
            print(f"Error fetching Arı24 events: {e}")
            return []

    def get_weekly_events(self):
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

        for ev in events:
            if ev["date_dt"]:
                # Check if event is within range AND in the future/today
                # logic: event must be >= start_date (Today) AND <= end_date (Next Sunday)
                if start_date <= ev["date_dt"] <= end_date:
                    data.append(ev)
            else:
                # If date parsing failed, maybe include?
                # Better safe than sorry, but might spam. Let's include if unsure.
                pass
        return data

    def get_upcoming_events(self):
        """Returns events that represent 'this week' or future."""
        events = self.get_events()
        data = []
        for ev in events:
            if ev["date_dt"]:
                data.append(ev)
            else:
                data.append(ev)
        return data

    def get_all_clubs(self) -> list[str]:
        """Extracts unique list of organizers/clubs from current events + data/ari24_clubs.json."""
        events = self.get_events()
        active_clubs = {ev["organizer"] for ev in events if ev["organizer"]}
        static_clubs = set(_load_static_clubs())
        return sorted(static_clubs | active_clubs)

    def get_news(self, limit=5):
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

                # Try to get image
                image_url = ""
                figure = item.find("figure")
                if figure:
                    style = figure.get("style", "")
                    match = re.search(r"url\((.*?)\)", style)
                    if match:
                        image_url = match.group(1).strip("'\"")
                        if not image_url.startswith("http"):
                            image_url = self.BASE_URL + image_url

                news.append({"title": title, "link": link, "image_url": image_url})

                if len(news) >= limit:
                    break

            return news
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []
