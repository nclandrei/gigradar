import re
from datetime import datetime

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://www.control-club.ro"
EVENTS_URL = f"{BASE_URL}/events/"


def parse_date_header(header_text: str) -> datetime | None:
    """Parse date from header like 'Thursday, January 15, 2026'."""
    try:
        cleaned = header_text.strip()
        return datetime.strptime(cleaned, "%A, %B %d, %Y")
    except ValueError:
        return None


def extract_artist_from_title(title: str) -> str | None:
    """Extract artist name from event title."""
    title = re.sub(r"^LIVE:\s*", "", title)
    
    separators = [" - ", " – ", " | ", " @ ", ": ", " w/ "]
    for sep in separators:
        if sep in title:
            return title.split(sep)[0].strip()
    return title


def parse_price(event_div: BeautifulSoup) -> str | None:
    """Extract price from event card."""
    price_elem = event_div.select_one(".ticket-price.price")
    if not price_elem:
        price_elem = event_div.select_one(".ticket-price-cockpit.price")
    
    if price_elem:
        price_text = price_elem.get_text(strip=True)
        price_text = re.sub(r"\s*\+\s*taxe", "", price_text)
        return price_text
    
    if event_div.select_one(".tag.black"):
        tag_text = event_div.select_one(".tag.black").get_text(strip=True)
        if "FREE" in tag_text.upper():
            return "Free"
        if "DOOR" in tag_text.upper():
            return "Door ticket"
    
    return None


def parse_event(event_div: BeautifulSoup, event_date: datetime, room: str) -> Event | None:
    """Parse a single event from HTML."""
    title_elem = event_div.select_one("a.title.hover")
    if not title_elem:
        return None
    
    title = title_elem.get_text(strip=True)
    href = title_elem.get("href", "")
    url = BASE_URL + href if href.startswith("/") else href
    
    artist = extract_artist_from_title(title)
    price = parse_price(event_div)
    venue = f"Control Club - {room}"
    
    return Event(
        title=title,
        artist=artist,
        venue=venue,
        date=event_date,
        url=url,
        source="control",
        category="music",
        price=price,
    )


def scrape() -> list[Event]:
    """Fetch upcoming events from Control Club."""
    events: list[Event] = []
    seen_urls: set[str] = set()
    
    try:
        html = fetch_page(EVENTS_URL, needs_js=True)
    except Exception as e:
        print(f"Failed to fetch Control Club events: {e}")
        return events
    
    soup = BeautifulSoup(html, "html.parser")
    
    list_view = soup.select_one(".events-list-view")
    if not list_view:
        print("Could not find events list view")
        return events
    
    for date_section in list_view.select(".date"):
        date_header = date_section.select_one(".title p")
        if not date_header:
            continue
        
        event_date = parse_date_header(date_header.get_text(strip=True))
        if not event_date:
            continue
        
        for room_section in date_section.select(".room"):
            room_title = room_section.select_one("p.title")
            room = room_title.get_text(strip=True) if room_title else "Unknown"
            
            for event_div in room_section.select(".event"):
                event = parse_event(event_div, event_date, room)
                if event and event.url not in seen_urls:
                    seen_urls.add(event.url)
                    events.append(event)
    
    return events
