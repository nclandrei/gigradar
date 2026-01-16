import re
from datetime import datetime

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://www.mnac.ro"
EVENTS_URL = f"{BASE_URL}/event-list/93/EVENIMENTE/67/events/1"


def parse_timestamp(timestamp_ms: str) -> datetime | None:
    """Parse Unix timestamp in milliseconds to datetime."""
    try:
        ts = int(timestamp_ms)
        return datetime.fromtimestamp(ts / 1000)
    except (ValueError, TypeError, OSError):
        return None


def parse_event(container: BeautifulSoup) -> Event | None:
    """Parse a single event from listEvents container."""
    link = container.select_one("a[href^='/event/']")
    if not link:
        return None

    href = link.get("href", "")
    if not href:
        return None
    url = BASE_URL + href

    title_elem = container.select_one(".title")
    if not title_elem:
        return None
    title = title_elem.get_text(strip=True)
    if not title:
        return None

    if title.startswith("[ANULAT]"):
        return None

    date_elem = container.select_one("vbn-date-format")
    if not date_elem:
        return None
    
    start_ts = date_elem.get("ng-reflect-start-date")
    if not start_ts:
        return None
    
    event_date = parse_timestamp(start_ts)
    if not event_date:
        return None

    if event_date < datetime.now():
        return None

    event_type_elem = container.select_one(".eventType")
    event_type = event_type_elem.get_text(strip=True) if event_type_elem else None

    return Event(
        title=title,
        artist=None,
        venue="MNAC",
        date=event_date,
        url=url,
        source="mnac",
        category="culture",
        price=event_type,
    )


def scrape() -> list[Event]:
    """Fetch upcoming events from MNAC."""
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()

    try:
        html = fetch_page(EVENTS_URL, needs_js=True, timeout=60000)
    except Exception as e:
        print(f"Failed to fetch MNAC events: {e}")
        return events

    soup = BeautifulSoup(html, "html.parser")

    for section_id in ["#currentEvent", "#futureEvent"]:
        section = soup.select_one(section_id)
        if not section:
            continue

        for container in section.select(".listEvents"):
            event = parse_event(container)
            if event:
                key = (event.title, event.date.isoformat())
                if key not in seen:
                    seen.add(key)
                    events.append(event)

    events.sort(key=lambda e: e.date)

    return events
