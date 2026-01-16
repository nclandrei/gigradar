import re
from datetime import datetime

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://arcub.ro"
AGENDA_URL = f"{BASE_URL}/agenda"

ROMANIAN_MONTHS = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4,
    "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
    "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12,
}


def parse_date(date_text: str) -> datetime | None:
    """Parse date from Romanian format like '17 ianuarie' or '15 - 17 ianuarie'."""
    date_text = date_text.strip().lower()
    
    range_match = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})\s+(\w+)", date_text)
    if range_match:
        end_day = int(range_match.group(2))
        month_name = range_match.group(3)
        month = ROMANIAN_MONTHS.get(month_name)
        if not month:
            return None
        year = datetime.now().year
        try:
            event_date = datetime(year, month, end_day, 19, 0)
            if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                event_date = datetime(year + 1, month, end_day, 19, 0)
            return event_date
        except ValueError:
            return None
    
    single_match = re.match(r"(\d{1,2})\s+(\w+)", date_text)
    if single_match:
        day = int(single_match.group(1))
        month_name = single_match.group(2)
        month = ROMANIAN_MONTHS.get(month_name)
        if not month:
            return None
        year = datetime.now().year
        try:
            event_date = datetime(year, month, day, 19, 0)
            if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                event_date = datetime(year + 1, month, day, 19, 0)
            return event_date
        except ValueError:
            return None
    
    return None


def parse_event(card: BeautifulSoup) -> Event | None:
    """Parse a single event from the project-box card."""
    link = card.select_one("a")
    if not link:
        return None
    
    url = link.get("href", "")
    if not url:
        return None
    if not url.startswith("http"):
        url = BASE_URL + url
    
    title_elem = card.select_one("h3")
    if not title_elem:
        return None
    title = title_elem.get_text(strip=True)
    if not title:
        return None
    
    meta = card.select_one(".meta")
    if not meta:
        return None
    
    spans = meta.select("span")
    if not spans:
        return None
    
    date_text = spans[0].get_text(strip=True) if spans else ""
    venue_text = spans[1].get_text(strip=True) if len(spans) > 1 else ""
    
    event_date = parse_date(date_text)
    if not event_date:
        return None
    
    venue = venue_text if venue_text else "ARCUB"
    
    return Event(
        title=title,
        artist=None,
        venue=venue,
        date=event_date,
        url=url,
        source="arcub",
        category="culture",
        price=None,
    )


def scrape() -> list[Event]:
    """Fetch upcoming events from ARCUB."""
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()
    
    try:
        html = fetch_page(AGENDA_URL, needs_js=True, timeout=60000)
    except Exception as e:
        print(f"Failed to fetch ARCUB events: {e}")
        return events
    
    soup = BeautifulSoup(html, "html.parser")
    
    for card in soup.select(".project-box"):
        event = parse_event(card)
        if event:
            key = (event.title, event.date.isoformat())
            if key not in seen:
                seen.add(key)
                events.append(event)
    
    events.sort(key=lambda e: e.date)
    
    return events
