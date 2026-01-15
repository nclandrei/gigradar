import re
from datetime import datetime
from urllib.parse import unquote

from bs4 import BeautifulSoup

from models import Event
from services.http import fetch_page

BASE_URL = "https://expirat.org"
SCHEDULE_URL = f"{BASE_URL}/schedule/events-live-act/"

ROMANIAN_DAYS = {
    "luni": 0, "marți": 1, "miercuri": 2, "joi": 3,
    "vineri": 4, "sâmbătă": 5, "duminică": 6,
}

ROMANIAN_MONTHS = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4,
    "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
    "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12,
}


def parse_date(date_str: str) -> datetime | None:
    """Parse Romanian date format (e.g., 'miercuri 11 decembrie')."""
    if not date_str:
        return None
    
    match = re.match(r"(\w+)\s+(\d{1,2})\s+(\w+)", date_str.strip().lower())
    if not match:
        return None
    
    day_name, day, month_name = match.groups()
    
    month = ROMANIAN_MONTHS.get(month_name)
    if not month:
        return None
    
    year = datetime.now().year
    try:
        event_date = datetime(year, month, int(day))
        if event_date < datetime.now():
            event_date = datetime(year + 1, month, int(day))
        return event_date
    except ValueError:
        return None


def extract_event_url(article: BeautifulSoup) -> str | None:
    """Extract event URL from sharing links."""
    share_link = article.select_one('a.facebook[href*="sharer.php"]')
    if share_link:
        href = share_link.get("href", "")
        match = re.search(r"[?&]u=([^&]+)", href)
        if match:
            return unquote(match.group(1))
    
    email_link = article.select_one('a.email[href^="mailto:"]')
    if email_link:
        href = email_link.get("href", "")
        match = re.search(r"body=([^&]+)", href)
        if match:
            return unquote(match.group(1))
    
    return None


def extract_tickets_url(article: BeautifulSoup) -> str | None:
    """Extract tickets URL from custom data fields."""
    tickets_link = article.select_one('.mec-event-data-field-item a[href*="iabilet"], .mec-event-data-field-item a[href*="eventbook"], .mec-event-data-field-item a[href*="rockstadt"]')
    if tickets_link:
        return tickets_link.get("href")
    
    for link in article.select('.mec-event-data-field-item a'):
        text = link.get_text(strip=True).lower()
        if "ticket" in text or "bilet" in text:
            return link.get("href")
    
    return None


def extract_artist_from_title(title: str) -> str | None:
    """Extract artist name from event title."""
    title = re.sub(r"^SOLD\s*OUT\s*[•·\-–]\s*", "", title, flags=re.I).strip()
    
    separators = [" • ", " · ", " - ", " – ", " | "]
    for sep in separators:
        if sep in title:
            return title.split(sep)[0].strip()
    return title


def parse_event_article(article: BeautifulSoup) -> Event | None:
    """Parse a single MEC event article."""
    title_elem = article.select_one("h4.mec-event-title")
    if not title_elem:
        return None
    title = title_elem.get_text(strip=True)
    
    date_elem = article.select_one(".mec-start-date-label")
    if not date_elem:
        return None
    event_date = parse_date(date_elem.get_text(strip=True))
    if not event_date:
        return None
    
    venue_elem = article.select_one(".mec-grid-event-location")
    venue = "Expirat"
    if venue_elem:
        venue_text = venue_elem.get_text(strip=True)
        if venue_text:
            venue = venue_text.split(",")[0].strip()
    
    url = extract_event_url(article)
    if not url:
        return None
    
    tickets_url = extract_tickets_url(article)
    
    artist = extract_artist_from_title(title)
    
    return Event(
        title=title,
        artist=artist,
        venue=venue,
        date=event_date,
        url=url,
        source="expirat",
        category="music",
        price=None,
    )


def scrape() -> list[Event]:
    """Fetch upcoming events from Expirat."""
    events: list[Event] = []
    seen_urls: set[str] = set()
    
    try:
        html = fetch_page(SCHEDULE_URL, needs_js=True)
    except Exception as e:
        print(f"Failed to fetch Expirat schedule: {e}")
        return events
    
    soup = BeautifulSoup(html, "html.parser")
    
    articles = soup.select(".mec-event-article")
    for article in articles:
        event = parse_event_article(article)
        if event and event.url not in seen_urls:
            seen_urls.add(event.url)
            events.append(event)
    
    return events
