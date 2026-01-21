"""Enrichment service for theatre/culture events.

Fetches descriptions, images, and videos from event detail pages.
Falls back to Gemini AI for generating descriptions when none found.
"""

import json
import os
import re
from dataclasses import replace

from bs4 import BeautifulSoup
from google import genai

from models import Event
from services.http import fetch_page, HttpError


def extract_bulandra(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from Bulandra event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # Image: gallery carousel links with wp-content/uploads
    gallery_links = soup.select("a[href*='wp-content/uploads']")
    for link in gallery_links:
        href = link.get("href", "")
        if href and any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            result["image_url"] = href
            break
    
    # Fallback to og:image
    if not result["image_url"]:
        og_image = soup.select_one("meta[property='og:image']")
        if og_image and og_image.get("content"):
            result["image_url"] = og_image["content"]
    
    # Video: YouTube links (not iframes - Bulandra uses direct links)
    video_link = soup.select_one("a[href*='youtube.com/watch'], a[href*='youtu.be']")
    if video_link:
        href = video_link.get("href", "")
        # Convert watch URL to embed format
        if "youtube.com/watch" in href:
            video_id = re.search(r'v=([^&]+)', href)
            if video_id:
                result["video_url"] = f"https://www.youtube.com/embed/{video_id.group(1)}"
        elif "youtu.be" in href:
            video_id = href.split("/")[-1].split("?")[0]
            result["video_url"] = f"https://www.youtube.com/embed/{video_id}"
    
    # Also check for iframe embeds
    if not result["video_url"]:
        iframe = soup.select_one("iframe[src*='youtube']")
        if iframe and iframe.get("src"):
            result["video_url"] = iframe["src"]
    
    # Description: Bulandra uses eael-tabs with #intro-tab containing the synopsis
    intro_tab = soup.select_one("#intro-tab, .eael-tab-content-item.active")
    if intro_tab:
        # Get paragraphs from the intro tab
        paragraphs = intro_tab.select("p")
        texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        if texts:
            result["description"] = " ".join(texts[:2])
    
    # Fallback: og:description
    if not result["description"]:
        og_desc = soup.select_one("meta[property='og:description']")
        if og_desc and og_desc.get("content"):
            result["description"] = og_desc["content"]
    
    return result


def extract_arcub(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from ARCUB event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # Image: try og:image first, then look for project images
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    else:
        img = soup.select_one(".project-image img, .event-image img, article img")
        if img and img.get("src"):
            result["image_url"] = img["src"]
    
    # Video: YouTube or Vimeo embeds
    iframe = soup.select_one("iframe[src*='youtube'], iframe[src*='vimeo']")
    if iframe and iframe.get("src"):
        result["video_url"] = iframe["src"]
    
    # Description: main content paragraphs
    content_sections = soup.select("article p, .content p, .event-description p, .post-content p")
    texts = []
    for p in content_sections:
        text = p.get_text(strip=True)
        if len(text) > 30:
            texts.append(text)
    
    if texts:
        result["description"] = " ".join(texts[:4])
    
    return result


def extract_mnac(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from MNAC event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # MNAC is Angular-based, may need JS rendering
    # Try og:image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    
    # Try meta description as fallback
    meta_desc = soup.select_one("meta[name='description']")
    if meta_desc and meta_desc.get("content"):
        result["description"] = meta_desc["content"]
    
    return result


def extract_metropolis(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from Teatrul Metropolis event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # Image: og:image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    
    # Description: og:description
    og_desc = soup.select_one("meta[property='og:description']")
    if og_desc and og_desc.get("content"):
        result["description"] = og_desc["content"]
    
    # Video: YouTube watch links (trailer)
    video_link = soup.select_one("a[href*='youtube.com/watch'], a[href*='youtu.be']")
    if video_link:
        href = video_link.get("href", "")
        if "youtube.com/watch" in href:
            video_id = re.search(r'v=([^&]+)', href)
            if video_id:
                result["video_url"] = f"https://www.youtube.com/embed/{video_id.group(1)}"
        elif "youtu.be" in href:
            video_id = href.split("/")[-1].split("?")[0]
            result["video_url"] = f"https://www.youtube.com/embed/{video_id}"
    
    return result


def extract_nottara(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from Teatrul Nottara event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # Image: og:image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    
    # Description: og:description
    og_desc = soup.select_one("meta[property='og:description']")
    if og_desc and og_desc.get("content"):
        result["description"] = og_desc["content"]
    
    # Video: YouTube embeds or links
    video_link = soup.select_one("a[href*='youtube.com/watch'], a[href*='youtu.be']")
    if video_link:
        href = video_link.get("href", "")
        if "youtube.com/watch" in href:
            video_id = re.search(r'v=([^&]+)', href)
            if video_id:
                result["video_url"] = f"https://www.youtube.com/embed/{video_id.group(1)}"
        elif "youtu.be" in href:
            video_id = href.split("/")[-1].split("?")[0]
            result["video_url"] = f"https://www.youtube.com/embed/{video_id}"
    
    # Fallback to iframe
    if not result["video_url"]:
        iframe = soup.select_one("iframe[src*='youtube']")
        if iframe and iframe.get("src"):
            result["video_url"] = iframe["src"]
    
    return result


def extract_tnb(soup: BeautifulSoup, url: str) -> dict:
    """Extract enrichment data from Teatrul Național București (TNB) event pages."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # TNB is Angular-based, limited scraping capability
    # Image: og:image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    
    # Description: og:description or meta description
    og_desc = soup.select_one("meta[property='og:description']")
    if og_desc and og_desc.get("content"):
        result["description"] = og_desc["content"]
    else:
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc and meta_desc.get("content"):
            result["description"] = meta_desc["content"]
    
    return result


def extract_generic(soup: BeautifulSoup, url: str) -> dict:
    """Generic extractor for unknown sources."""
    result: dict = {"description": None, "image_url": None, "video_url": None}
    
    # Try og:image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        result["image_url"] = og_image["content"]
    
    # Try og:description or meta description
    og_desc = soup.select_one("meta[property='og:description']")
    if og_desc and og_desc.get("content"):
        result["description"] = og_desc["content"]
    else:
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc and meta_desc.get("content"):
            result["description"] = meta_desc["content"]
    
    # Look for video embeds (iframes)
    iframe = soup.select_one("iframe[src*='youtube'], iframe[src*='vimeo']")
    if iframe and iframe.get("src"):
        result["video_url"] = iframe["src"]
    
    # Also look for video links
    if not result["video_url"]:
        video_link = soup.select_one("a[href*='youtube.com/watch'], a[href*='youtu.be']")
        if video_link:
            href = video_link.get("href", "")
            if "youtube.com/watch" in href:
                video_id = re.search(r'v=([^&]+)', href)
                if video_id:
                    result["video_url"] = f"https://www.youtube.com/embed/{video_id.group(1)}"
            elif "youtu.be" in href:
                video_id = href.split("/")[-1].split("?")[0]
                result["video_url"] = f"https://www.youtube.com/embed/{video_id}"
    
    return result


# Map source names to their extractors
SOURCE_EXTRACTORS = {
    "bulandra": extract_bulandra,
    "arcub": extract_arcub,
    "mnac": extract_mnac,
    "metropolis": extract_metropolis,
    "nottara": extract_nottara,
    "tnb": extract_tnb,
}


def scrape_event_details(event: Event) -> dict:
    """Fetch and extract enrichment data from event detail page."""
    if not event.url:
        return {"description": None, "image_url": None, "video_url": None}
    
    try:
        # Most theatre sites need JS rendering
        html = fetch_page(event.url, needs_js=True, timeout=15000)
    except HttpError as e:
        print(f"  Failed to fetch {event.url}: {e}")
        return {"description": None, "image_url": None, "video_url": None}
    except Exception as e:
        print(f"  Unexpected error fetching {event.url}: {e}")
        return {"description": None, "image_url": None, "video_url": None}
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Use source-specific extractor if available
    extractor = SOURCE_EXTRACTORS.get(event.source, extract_generic)
    return extractor(soup, event.url)


def generate_ai_description(event: Event) -> str | None:
    """Generate description using Gemini AI."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    
    client = genai.Client(api_key=api_key)
    
    prompt = f"""Ești un critic de teatru și cultură din București. 
Generează o descriere scurtă și captivantă (2-3 propoziții, max 150 cuvinte) pentru acest eveniment:

Titlu: {event.title}
Locație: {event.venue}
Categorie: {"Teatru" if event.category == "theatre" else "Cultură"}
{f"Artist/Autor: {event.artist}" if event.artist else ""}

Descrierea trebuie să fie în limba română, să sune natural și să incite curiozitatea spectatorului.
Nu inventa detalii specifice despre intrigă sau distribuție dacă nu sunt menționate.
Răspunde DOAR cu descrierea, fără prefixe sau explicații."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = response.text.strip()
        # Clean up any markdown or quotes
        text = re.sub(r'^["\']|["\']$', '', text)
        return text if len(text) > 20 else None
    except Exception as e:
        print(f"  AI description failed for {event.title}: {e}")
        return None


def enrich_event(event: Event) -> Event:
    """Enrich a single event with description, image, and video."""
    # Skip music events
    if event.category == "music":
        return event
    
    # Skip if already enriched
    if event.description or event.image_url or event.video_url:
        return event
    
    # Try to scrape from source page
    details = scrape_event_details(event)
    
    description = details.get("description")
    description_source = "scraped" if description else None
    
    # If no description found, try AI fallback
    if not description:
        description = generate_ai_description(event)
        if description:
            description_source = "ai"
    
    # Truncate long descriptions
    if description and len(description) > 500:
        description = description[:497] + "..."
    
    return replace(
        event,
        description=description,
        description_source=description_source,
        image_url=details.get("image_url"),
        video_url=details.get("video_url"),
    )


def enrich_events(events: list[Event]) -> list[Event]:
    """Enrich all theatre/culture events with additional details."""
    enriched: list[Event] = []
    
    theatre_culture = [e for e in events if e.category in ("theatre", "culture")]
    total = len(theatre_culture)
    
    for i, event in enumerate(events):
        if event.category in ("theatre", "culture"):
            print(f"  [{i+1}/{total}] Enriching: {event.title[:40]}...", end=" ", flush=True)
            enriched_event = enrich_event(event)
            status = "✓" if enriched_event.description or enriched_event.image_url else "○"
            print(status)
            enriched.append(enriched_event)
        else:
            enriched.append(event)
    
    return enriched
