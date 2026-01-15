#!/usr/bin/env python3
"""GigRadar: Weekly event aggregator matching Spotify followed artists."""

import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from rapidfuzz import fuzz

from models import Event
from scrapers.music import control, expirat, iabilet, jfr, quantic
from scrapers.theatre import bulandra
from services.dedup import llm_dedup, stage1_dedup
from services.email import send_digest
from services.spotify import get_followed_artists, normalize

DATA_DIR = Path(__file__).parent / "data"
RETENTION_DAYS = 7


def run_music_scrapers() -> list[Event]:
    """Run all music scrapers and collect events."""
    events: list[Event] = []
    for scraper in [iabilet, control, expirat, quantic, jfr]:
        events.extend(scraper.scrape())
    return events


def run_theatre_scrapers() -> list[Event]:
    """Run all theatre scrapers and collect events."""
    events: list[Event] = []
    for scraper in [bulandra]:
        events.extend(scraper.scrape())
    return events


def match_events(events: list[Event], artists: list[str]) -> list[Event]:
    """Filter events to those matching followed artists."""
    artist_set = {normalize(a) for a in artists}

    matched: list[Event] = []
    for event in events:
        if not event.artist:
            continue

        normalized_artist = normalize(event.artist)
        if normalized_artist in artist_set:
            matched.append(event)
            continue

        for artist in artist_set:
            if fuzz.ratio(normalized_artist, artist) > 85:
                matched.append(event)
                break

    return matched


def load_previous_events() -> set[str]:
    """Load event keys from the most recent JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)

    if not files:
        return set()

    with open(files[0]) as f:
        data = json.load(f)

    keys: set[str] = set()
    for event in data.get("music_events", []) + data.get("theatre_events", []):
        key = f"{event['artist']}|{event['date']}|{event['venue']}"
        keys.add(key)

    return keys


def save_results(
    music_events: list[Event],
    theatre_events: list[Event],
    artists: list[str],
) -> None:
    """Save results to a date-prefixed JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = DATA_DIR / f"{today}.json"

    data = {
        "scraped_at": datetime.now().isoformat(),
        "music_events": [asdict(e) for e in music_events],
        "theatre_events": [asdict(e) for e in theatre_events],
        "spotify_artists": artists,
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
    print("Fetching Spotify followed artists...")
    artists = get_followed_artists()
    print(f"Found {len(artists)} followed artists")

    print("Running music scrapers...")
    music_events = run_music_scrapers()
    print(f"Found {len(music_events)} music events")

    print("Matching events to followed artists...")
    matched_music = match_events(music_events, artists)
    print(f"Matched {len(matched_music)} events to followed artists")

    print("Running theatre scrapers...")
    theatre_events = run_theatre_scrapers()
    print(f"Found {len(theatre_events)} theatre events")

    print("Deduplicating events...")
    deduped_music = stage1_dedup(matched_music)
    deduped_music = llm_dedup(deduped_music)
    deduped_theatre = stage1_dedup(theatre_events)
    print(f"After dedup: {len(deduped_music)} music, {len(deduped_theatre)} theatre")

    print("Loading previous results...")
    previous_keys = load_previous_events()

    new_music = get_new_events(deduped_music, previous_keys)
    new_theatre = get_new_events(deduped_theatre, previous_keys)
    print(f"New events: {len(new_music)} music, {len(new_theatre)} theatre")

    if new_music or new_theatre:
        print("Sending email digest...")
        to_email = os.environ.get("NOTIFY_EMAIL", "")
        if to_email:
            send_digest(new_music, new_theatre, to_email)
            print("Email sent!")
        else:
            print("NOTIFY_EMAIL not set, skipping email")

    print("Saving results...")
    save_results(deduped_music, deduped_theatre, artists)

    print("Cleaning up old files...")
    cleanup_old_files()

    print("Done!")


if __name__ == "__main__":
    main()
