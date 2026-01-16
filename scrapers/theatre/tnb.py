import re
from datetime import datetime

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://www.tnb.ro"
CALENDAR_URL = f"{BASE_URL}/ro/calendar"


def get_calendar_url(year: int, month: int) -> str:
    """Build calendar URL for given year and month."""
    return f"{CALENDAR_URL}?year={year}&month={month}"


def parse_time(time_text: str) -> tuple[int, int]:
    """Parse time like 'Ora: 19:00' or 'Ora:  18:30'."""
    match = re.search(r"(\d{1,2}):(\d{2})", time_text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 19, 0


def parse_event(event_elem: BeautifulSoup, event_date: datetime) -> Event | None:
    """Parse a single event from the calendar cell."""
    tooltip = event_elem.select_one(".toltip_text")
    if not tooltip:
        return None
    
    title_elem = tooltip.select_one("h3")
    if not title_elem:
        return None
    
    title = title_elem.get_text(strip=True)
    if not title:
        return None
    
    link_elem = tooltip.select_one("a[href]")
    url = ""
    if link_elem:
        url = link_elem.get("href", "")
        if url and not url.startswith("http"):
            url = BASE_URL + url
    
    hour_elem = tooltip.select_one(".hour")
    hour, minute = 19, 0
    if hour_elem:
        hour, minute = parse_time(hour_elem.get_text(strip=True))
    
    event_datetime = event_date.replace(hour=hour, minute=minute)
    
    location_elem = tooltip.select_one(".location")
    hall = location_elem.get_text(strip=True) if location_elem else ""
    if hall.startswith("TNB - "):
        venue = hall
    elif hall:
        venue = f"TNB - {hall}"
    else:
        venue = "TNB"
    
    return Event(
        title=title,
        artist=None,
        venue=venue,
        date=event_datetime,
        url=url,
        source="tnb",
        category="theatre",
        price=None,
    )


def scrape_month(year: int, month: int) -> list[Event]:
    """Scrape events for a specific month."""
    events: list[Event] = []
    
    url = get_calendar_url(year, month)
    try:
        html = fetch_page(url, needs_js=True, timeout=60000)
    except Exception as e:
        print(f"Failed to fetch TNB calendar for {year}/{month}: {e}")
        return events
    
    soup = BeautifulSoup(html, "html.parser")
    
    for week_row in soup.select(".fc-week"):
        day_cells = week_row.select("td[data-date]")
        event_cells = week_row.select(".fc-content-skeleton td")
        
        date_to_events: dict[str, list[BeautifulSoup]] = {}
        
        for cell in week_row.select(".fc-content-skeleton tbody td"):
            events_in_cell = cell.select(".fc-day-grid-event")
            if events_in_cell:
                parent_table = cell.find_parent("table")
                if parent_table:
                    thead = parent_table.select_one("thead tr")
                    if thead:
                        cell_idx = 0
                        for sibling in cell.previous_siblings:
                            if hasattr(sibling, 'name') and sibling.name == 'td':
                                cell_idx += 1
                        date_tds = thead.select("td[data-date]")
                        if cell_idx < len(date_tds):
                            date_str = date_tds[cell_idx].get("data-date", "")
                            if date_str:
                                if date_str not in date_to_events:
                                    date_to_events[date_str] = []
                                date_to_events[date_str].extend(events_in_cell)
        
        for date_str, event_elems in date_to_events.items():
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            
            for event_elem in event_elems:
                event = parse_event(event_elem, event_date)
                if event:
                    events.append(event)
    
    return events


def scrape() -> list[Event]:
    """Fetch upcoming events from Teatrul Național București."""
    events: list[Event] = []
    seen: set[tuple[str, str, str]] = set()
    
    now = datetime.now()
    months_to_scrape = [
        (now.year, now.month),
        (now.year if now.month < 12 else now.year + 1, (now.month % 12) + 1),
    ]
    
    for year, month in months_to_scrape:
        month_events = scrape_month(year, month)
        for event in month_events:
            key = (event.title, event.date.isoformat(), event.venue)
            if key not in seen:
                seen.add(key)
                events.append(event)
    
    events = [e for e in events if e.date >= now.replace(hour=0, minute=0, second=0, microsecond=0)]
    events.sort(key=lambda e: e.date)
    
    return events
