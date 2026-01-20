#!/usr/bin/env python3
"""Cultură la plic: Weekly event aggregator for Bucharest cultural events."""

import json
import os
import traceback
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

from models import Event
from scrapers.culture import arcub, mnac
from scrapers.music import control, enescu, expirat, garana, jazzinthepark, jazzx, jfr, quantic
from scrapers.theatre import bulandra
from services.dedup import llm_dedup, stage1_dedup
from services.email import ScraperError, send_digest, send_scraper_alert
from services.spotify import search_artist

DATA_DIR = Path(__file__).parent / "data"
RETENTION_DAYS = 7
FESTIVAL_SCRAPERS = {garana, jazzinthepark, jfr}

scraper_errors: list[ScraperError] = []


def should_run_festival_scrapers() -> bool:
    """Run festival scrapers only on the 1st of each month (annual events don't change often)."""
    return datetime.now().day == 1


def run_scraper_safely(scraper: ModuleType) -> list[Event]:
    """Run a single scraper, catching and recording any errors."""
    scraper_name = scraper.__name__.split(".")[-1]
    try:
        return scraper.scrape()
    except Exception as e:
        tb = traceback.format_exc()
        error = ScraperError(
            scraper_name=scraper_name,
            error_message=str(e),
            traceback=tb,
        )
        scraper_errors.append(error)
        print(f"⚠️  Scraper '{scraper_name}' failed: {e}")
        return []


def run_music_scrapers() -> list[Event]:
    """Run all music scrapers and collect events."""
    events: list[Event] = []
    all_scrapers = [control, enescu, expirat, quantic, jfr, garana, jazzinthepark, jazzx]
    run_festivals = should_run_festival_scrapers()
    
    for scraper in all_scrapers:
        if scraper in FESTIVAL_SCRAPERS and not run_festivals:
            continue
        events.extend(run_scraper_safely(scraper))
    
    if not run_festivals:
        print("  (skipping festival scrapers - only run on 1st of month)")
    return events


def run_theatre_scrapers() -> list[Event]:
    """Run all theatre scrapers and collect events."""
    events: list[Event] = []
    for scraper in [bulandra]:
        events.extend(run_scraper_safely(scraper))
    return events


def run_culture_scrapers() -> list[Event]:
    """Run all culture scrapers and collect events."""
    events: list[Event] = []
    for scraper in [arcub, mnac]:
        events.extend(run_scraper_safely(scraper))
    return events


def enrich_with_spotify(events: list[Event]) -> list[Event]:
    """Add Spotify URLs to music events where artist is found."""
    enriched: list[Event] = []
    for event in events:
        if event.category == "music" and event.artist:
            spotify_url = search_artist(event.artist)
            enriched.append(replace(event, spotify_url=spotify_url))
        else:
            enriched.append(event)
    return enriched


def load_previous_events() -> set[str]:
    """Load event keys from the most recent JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)

    if not files:
        return set()

    with open(files[0]) as f:
        data = json.load(f)

    keys: set[str] = set()
    for event in data.get("music_events", []) + data.get("theatre_events", []) + data.get("culture_events", []):
        key = f"{event['artist']}|{event['date']}|{event['venue']}"
        keys.add(key)

    return keys


def save_results(
    music_events: list[Event],
    theatre_events: list[Event],
    culture_events: list[Event],
) -> None:
    """Save results to a date-prefixed JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = DATA_DIR / f"{today}.json"

    data = {
        "scraped_at": datetime.now().isoformat(),
        "music_events": [asdict(e) for e in music_events],
        "theatre_events": [asdict(e) for e in theatre_events],
        "culture_events": [asdict(e) for e in culture_events],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def cleanup_old_files() -> None:
    """Delete JSON files older than RETENTION_DAYS."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

    for filepath in DATA_DIR.glob("*.json"):
        try:
            date_str = filepath.stem
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                filepath.unlink()
        except ValueError:
            pass


def get_new_events(
    events: list[Event], previous_keys: set[str]
) -> list[Event]:
    """Filter to only new events not seen in previous run."""
    new_events: list[Event] = []
    for event in events:
        key = f"{event.artist}|{event.date.strftime('%Y-%m-%d')}|{event.venue}"
        if key not in previous_keys:
            new_events.append(event)
    return new_events


def main() -> None:
    """Main orchestrator."""
    print("Running music scrapers...")
    music_events = run_music_scrapers()
    print(f"Found {len(music_events)} music events")

    print("Running theatre scrapers...")
    theatre_events = run_theatre_scrapers()
    print(f"Found {len(theatre_events)} theatre events")

    print("Running culture scrapers...")
    culture_events = run_culture_scrapers()
    print(f"Found {len(culture_events)} culture events")

    print("Deduplicating events...")
    deduped_music = stage1_dedup(music_events)
    deduped_music = llm_dedup(deduped_music)
    deduped_theatre = stage1_dedup(theatre_events)
    deduped_culture = stage1_dedup(culture_events)
    print(f"After dedup: {len(deduped_music)} music, {len(deduped_theatre)} theatre, {len(deduped_culture)} culture")

    print("Enriching music events with Spotify links...")
    deduped_music = enrich_with_spotify(deduped_music)
    spotify_count = sum(1 for e in deduped_music if e.spotify_url)
    print(f"Found {spotify_count} artists on Spotify")

    print("Loading previous results...")
    previous_keys = load_previous_events()

    new_music = get_new_events(deduped_music, previous_keys)
    new_theatre = get_new_events(deduped_theatre, previous_keys)
    new_culture = get_new_events(deduped_culture, previous_keys)
    print(f"New events: {len(new_music)} music, {len(new_theatre)} theatre, {len(new_culture)} culture")

    if new_music or new_theatre or new_culture:
        print("Sending email digest...")
        to_email = os.environ.get("NOTIFY_EMAIL", "")
        if to_email:
            send_digest(new_music, new_theatre, new_culture, to_email)
            print("Email sent!")
        else:
            print("NOTIFY_EMAIL not set, skipping email")

    print("Saving results...")
    save_results(deduped_music, deduped_theatre, deduped_culture)

    print("Cleaning up old files...")
    cleanup_old_files()

    if scraper_errors:
        print(f"Sending alert for {len(scraper_errors)} failed scraper(s)...")
        to_email = os.environ.get("NOTIFY_EMAIL", "")
        if to_email:
            send_scraper_alert(scraper_errors, to_email)
            print("Alert sent!")
        else:
            print("NOTIFY_EMAIL not set, skipping alert")

    print("Done!")


if __name__ == "__main__":
    main()
