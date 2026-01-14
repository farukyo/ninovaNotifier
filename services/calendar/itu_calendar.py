import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class CalendarEvent:
    name: str
    date_str: str
    status: str
    is_past: bool

@dataclass
class CalendarSection:
    title: str
    events: List[CalendarEvent]

class ITUCalendarService:
    url = "https://www.takvim.sis.itu.edu.tr/AkademikTakvim/TR/akademik-takvim/AkademikTakvimTablo.php"

    @staticmethod
    def fetch_calendar() -> List[CalendarSection]:
        try:
            response = requests.get(ITUCalendarService.url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8' # Ensure correct encoding for Turkish chars
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='table table-bordered table-striped table-hover')
            
            if not table:
                return []

            sections: List[CalendarSection] = []
            current_section_title = "Genel"
            current_events: List[CalendarEvent] = []

            rows = table.find_all('tr')
            
            # Skip the first row if it is just table headers (Güz Dönemi, Tarih, Kalan Gün usually appears as first row or section header)
            
            for row in rows:
                cols = row.find_all('td')
                if not cols:
                    continue
                
                # Check if it is a header row
                # The user provided HTML showing class="tablo-baslik" for headers
                if cols[0].get('class') and 'tablo-baslik' in cols[0].get('class'):
                    # Save previous section if exists
                    if current_events:
                        sections.append(CalendarSection(title=current_section_title, events=current_events))
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
                    
                    event = CalendarEvent(name=name, date_str=date_str, status=status, is_past=is_past)
                    current_events.append(event)
            
            # Append the last section
            if current_events:
                sections.append(CalendarSection(title=current_section_title, events=current_events))

            return sections

        except Exception as e:
            print(f"Error fetching calendar: {e}")
            return []

    @staticmethod
    def get_filtered_calendar() -> str:
        sections = ITUCalendarService.fetch_calendar()
        if not sections:
            return "❌ Akademik takvim verisi alınamadı."

        output = []
        output.append("📚 <b>İTÜ AKADEMİK TAKVİM</b>")
        output.append("━━━━━━━━━━━━━━━━━━━━━")
        
        for section in sections:
            # Sadece "Lisans / Önlisans Akademik Takvimi" bölümünü göster
            if "lisans / önlisans" not in section.title.lower() and \
               "güz dönemi" not in section.title.lower() and \
               "bahar dönemi" not in section.title.lower():
                continue
                
            events = section.events
            if not events:
                continue
                
            # Find the transition point (first future event)
            first_future_index = len(events) 
            for i, event in enumerate(events):
                if not event.is_past:
                    first_future_index = i
                    break
            
            # Calculate indices for "past 5" and "next 10"
            start_index = max(0, first_future_index - 5)
            end_index = min(len(events), first_future_index + 10)
            
            filtered_events = events[start_index:end_index]
            
            if filtered_events:
                # Section header
                output.append("")
                output.append(f"📅 <b>{section.title}</b>")
                output.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
                
                for event in filtered_events:
                    # Determine icon based on status
                    icon = "✅" if event.is_past else "⏳"
                    status_text = event.status
                    
                    if "Devam ediyor" in event.status:
                        icon = "🔥"
                        status_text = f"<b>{event.status}</b>"
                    elif "kaldı" in event.status:
                        parts = event.status.split()
                        if parts and parts[0].isdigit():
                            days = int(parts[0])
                            if days <= 7:
                                icon = "🚨"
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
        output.append(f"🔗 <a href='{ITUCalendarService.url}'>Detaylı Takvim için Tıklayın</a>")
        return "\n".join(output)

if __name__ == "__main__":
    # Test run
    print(ITUCalendarService.get_filtered_calendar())
