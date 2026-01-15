from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class CalendarEvent:
    name: str
    date_str: str
    status: str
    is_past: bool


@dataclass
class CalendarSection:
    title: str
    events: list[CalendarEvent]


class ITUCalendarService:
    url = "https://www.takvim.sis.itu.edu.tr/AkademikTakvim/TR/akademik-takvim/AkademikTakvimTablo.php"

    @staticmethod
    def fetch_calendar() -> list[CalendarSection]:
        try:
            response = requests.get(ITUCalendarService.url, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"  # Ensure correct encoding for Turkish chars

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="table table-bordered table-striped table-hover")

            if not table:
                return []

            sections: list[CalendarSection] = []
            current_section_title = "Genel"
            current_events: list[CalendarEvent] = []

            rows = table.find_all("tr")

            # Skip the first row if it is just table headers (Güz Dönemi, Tarih, Kalan Gün usually appears as first row or section header)

            for row in rows:
                cols = row.find_all("td")
                if not cols:
                    continue

                # Check if it is a header row
                # The user provided HTML showing class="tablo-baslik" for headers
                if cols[0].get("class") and "tablo-baslik" in cols[0].get("class"):
                    # Save previous section if exists
                    if current_events:
                        sections.append(
                            CalendarSection(title=current_section_title, events=current_events)
                        )
                        current_events = []

                    current_section_title = cols[0].get_text(strip=True)
                    continue

                # It's a data row
                if len(cols) >= 3:
                    name = cols[0].get_text(strip=True)
                    date_str = cols[1].get_text(strip=True)
                    status = cols[2].get_text(strip=True)

                    # Skip rows that might be sub-headers without class (if any)
                    # Usually "Tarih" column header row
                    if name == "Güz Dönemi" or date_str == "Tarih":
                        continue

                    is_past = "geçti" in status.lower()

                    event = CalendarEvent(
                        name=name, date_str=date_str, status=status, is_past=is_past
                    )
                    current_events.append(event)

            # Append the last section
            if current_events:
                sections.append(CalendarSection(title=current_section_title, events=current_events))

            return sections

        except Exception as e:
            print(f"Error fetching calendar: {e}")
            return []

    @staticmethod
    def get_filtered_calendar(show_all: bool = False) -> str:
        from datetime import datetime

        from common.utils import parse_turkish_date

        sections = ITUCalendarService.fetch_calendar()
        if not sections:
            return "❌ Akademik takvim verisi alınamadı."

        output = []
        output.append("📚 <b>İTÜ AKADEMİK TAKVİM</b>")
        output.append("━━━━━━━━━━━━━━━━━━━━━")

        now = datetime.now()
        hidden_past_count = 0

        for section in sections:
            # Sadece "Lisans / Önlisans Akademik Takvimi" bölümünü göster
            if (
                "lisans / önlisans" not in section.title.lower()
                and "güz dönemi" not in section.title.lower()
                and "bahar dönemi" not in section.title.lower()
            ):
                continue

            events = section.events
            if not events:
                continue

            # Categorize events
            categorized_events = []
            for event in events:
                # Parse date for accurate categorization
                parsed_date = parse_turkish_date(event.date_str)

                # Determine category
                category = "past"
                days_until = None

                if event.is_past:
                    category = "past"
                elif "Devam ediyor" in event.status:
                    category = "ongoing"
                elif parsed_date:
                    days_until = (parsed_date - now).days
                    if days_until <= 7:
                        category = "starting_soon"
                    else:
                        category = "upcoming"
                else:
                    # No date parsed, check status
                    if "kaldı" in event.status:
                        # Extract days from status
                        parts = event.status.split()
                        if parts and parts[0].isdigit():
                            days_until = int(parts[0])
                            if days_until <= 7:
                                category = "starting_soon"
                            else:
                                category = "upcoming"
                    else:
                        category = "upcoming"

                categorized_events.append(
                    {"event": event, "category": category, "days_until": days_until}
                )

            # Filter events based on show_all
            visible_events = []
            for item in categorized_events:
                if show_all or item["category"] != "past":
                    visible_events.append(item)
                else:
                    hidden_past_count += 1

            if visible_events:
                # Section header
                output.append("")
                output.append(f"📅 <b>{section.title}</b>")
                output.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")

                for item in visible_events:
                    event = item["event"]
                    category = item["category"]

                    # Determine icon based on category
                    if category == "past":
                        icon = "❌"
                    elif category == "ongoing":
                        icon = "🔥"
                    elif category == "starting_soon":
                        icon = "🚨"
                    else:  # upcoming
                        icon = "📅"

                    status_text = event.status

                    # Bold important statuses
                    if category in ["ongoing", "starting_soon"]:
                        status_text = f"<b>{event.status}</b>"

                    # Truncate long event names
                    name = event.name
                    if len(name) > 60:
                        name = name[:57] + "..."

                    # Format event
                    output.append(f"{icon} <b>{name}</b>")
                    output.append(f"    📆 {event.date_str}")
                    output.append(f"    ⏱ {status_text}")
                    output.append("")

        output.append("━━━━━━━━━━━━━━━━━━━━━")

        # Add "Show All" hint if there are hidden events
        if hidden_past_count > 0 and not show_all:
            output.append(f"📜 <i>{hidden_past_count} geçmiş etkinlik gizlendi</i>")

        output.append(f"🔗 <a href='{ITUCalendarService.url}'>Detaylı Takvim için Tıklayın</a>")
        return "\n".join(output)


if __name__ == "__main__":
    # Test run
    print(ITUCalendarService.get_filtered_calendar())
