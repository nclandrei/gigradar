import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://www.iabilet.ro"
BUCHAREST_URL = f"{BASE_URL}/bilete-in-bucuresti/"
MAX_PAGES = 10

ROMANIAN_MONTHS = {
    "ian": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "iun": 6,
    "iul": 7, "aug": 8, "sep": 9, "oct": 10, "noi": 11, "dec": 12,
}


def parse_date(day: str, month: str, year: str | None = None) -> datetime:
    """Parse Romanian date format (e.g., '17', 'ian', "'26")."""
    month_num = ROMANIAN_MONTHS.get(month.lower(), 1)
    
    if year:
        year_num = int(year.replace("'", "").strip())
        if year_num < 100:
            year_num += 2000
    else:
        year_num = datetime.now().year
        test_date = datetime(year_num, month_num, int(day))
        if test_date < datetime.now():
            year_num += 1
    
    return datetime(year_num, month_num, int(day))


def extract_artist_from_title(title: str) -> str | None:
    """Extract artist name from event title."""
    separators = [" - ", " – ", " | ", " @ ", ": "]
    for sep in separators:
        if sep in title:
            return title.split(sep)[0].strip()
    return title


def parse_event_card(card: BeautifulSoup) -> Event | None:
    """Parse a single event card from the HTML."""
    title_elem = card.select_one(".title a span")
    if not title_elem:
        return None
    title = title_elem.get_text(strip=True)
    
    link_elem = card.select_one(".title a")
    if not link_elem:
        return None
    url = BASE_URL + link_elem.get("href", "").split("?")[0]
    
    venue_elem = card.select_one(".location .venue span")
    venue = venue_elem.get_text(strip=True) if venue_elem else "Unknown"
    
    date_elem = card.select_one(".date-start")
    if not date_elem:
        date_elem = card.select_one(".date")
    
    if date_elem:
        day_elem = date_elem.select_one(".date-day") or date_elem.select_one("span:first-child")
        month_elem = date_elem.select_one(".date-month") or date_elem.select_one("span:nth-child(2)")
        year_elem = date_elem.select_one(".date-year")
        
        if day_elem and month_elem:
            day = day_elem.get_text(strip=True)
            month = month_elem.get_text(strip=True)
            year = year_elem.get_text(strip=True) if year_elem else None
            event_date = parse_date(day, month, year)
        else:
            return None
    else:
        return None
    
    price_elem = card.select_one(".price")
    price = None
    if price_elem:
        price_text = price_elem.get_text(strip=True)
        if price_text:
            price = price_text
    
    artist = extract_artist_from_title(title)
    
    return Event(
        title=title,
        artist=artist,
        venue=venue,
        date=event_date,
        url=url,
        source="iabilet",
        category="music",
        price=price,
    )


def extract_json_ld_events(soup: BeautifulSoup) -> list[dict]:
    """Extract events from JSON-LD structured data."""
    events = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            text = script.string
            if not text:
                continue
            text = text.replace("/*<![CDATA[*/", "").replace("/*]]>*/", "").strip()
            data = json.loads(text)
            if data.get("@type") == "Event":
                events.append(data)
        except (json.JSONDecodeError, AttributeError):
            continue
    return events


def parse_json_ld_event(data: dict) -> Event | None:
    """Parse event from JSON-LD data."""
    try:
        title = data.get("name", "")
        url = data.get("url", "")
        
        location = data.get("location", {})
        venue = location.get("name", "Unknown") if isinstance(location, dict) else "Unknown"
        
        start_date_str = data.get("startDate", "")
        if start_date_str:
            event_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            return None
        
        offers = data.get("offers", {})
        price = None
        if isinstance(offers, dict) and offers.get("price"):
            price = f"{offers['price']} {offers.get('priceCurrency', 'RON')}"
        
        artist = extract_artist_from_title(title)
        
        return Event(
            title=title,
            artist=artist,
            venue=venue,
            date=event_date,
            url=url,
            source="iabilet",
            category="music",
            price=price,
        )
    except (ValueError, KeyError):
        return None


def scrape() -> list[Event]:
    """Fetch upcoming events from iaBilet."""
    events: list[Event] = []
    seen_urls: set[str] = set()
    
    for page in range(1, MAX_PAGES + 1):
        url = BUCHAREST_URL if page == 1 else f"{BUCHAREST_URL}?page={page}"
        
        try:
            html = fetch_page(url)
        except Exception as e:
            print(f"Failed to fetch iaBilet page {page}: {e}")
            break
        
        soup = BeautifulSoup(html, "html.parser")
        
        json_ld_events = extract_json_ld_events(soup)
        for data in json_ld_events:
            event = parse_json_ld_event(data)
            if event and event.url not in seen_urls:
                seen_urls.add(event.url)
                events.append(event)
        
        cards = soup.select('[data-event-list="item"]')
        for card in cards:
            event = parse_event_card(card)
            if event and event.url not in seen_urls:
                seen_urls.add(event.url)
                events.append(event)
        
        more_btn = soup.select_one('[data-event-list="more"] a')
        if not more_btn:
            break
    
    return events
