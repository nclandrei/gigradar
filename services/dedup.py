import re

from rapidfuzz import fuzz

from models import Event

# Canonical venue names -> list of known aliases/variations
VENUE_ALIASES: dict[str, list[str]] = {
    "control": ["control club", "control bucuresti", "club control"],
    "expirat": ["expirat club", "club expirat", "expirat halele carol"],
    "quantic": ["quantic club", "club quantic", "quantic bucuresti"],
    "hard rock cafe": ["hard rock cafe bucuresti", "hardrock cafe", "hard rock bucuresti"],
    "beraria h": ["beraria h bucuresti", "berăria h"],
    "arenele romane": ["arenele romane bucuresti"],
    "sala palatului": ["sala palatului bucuresti"],
    "romexpo": ["romexpo bucuresti", "pavilion romexpo"],
    "opera nationala bucuresti": ["opera nb", "opera nationala"],
    "grivita 53": ["g53", "teatrul grivita", "teatrul grivita 53"],
    "tnb": ["teatrul national bucuresti", "teatrul nb", "teatrul national"]
}

# Build reverse lookup: alias -> canonical name
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in VENUE_ALIASES.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias] = canonical


def sanitize_venue(venue: str) -> str:
    """Normalize venue name: lowercase, remove extra whitespace, punctuation."""
    venue = venue.lower().strip()
    venue = re.sub(r"[^\w\s]", "", venue)  # remove punctuation
    venue = re.sub(r"\s+", " ", venue)  # collapse whitespace
    return venue


def normalize_venue(venue: str) -> str:
    """Sanitize and resolve to canonical venue name if known."""
    sanitized = sanitize_venue(venue)
    return _ALIAS_TO_CANONICAL.get(sanitized, sanitized)


def normalize_for_dedup(event: Event) -> str:
    """Create a normalized key for exact deduplication."""
    artist = (event.artist or "").lower().strip()
    venue = normalize_venue(event.venue)
    date_str = event.date.strftime("%Y-%m-%d")
    return f"{artist}|{date_str}|{venue}"


def stage1_dedup(events: list[Event]) -> list[Event]:
    """Deduplicate using exact match and Levenshtein similarity."""
    if not events:
        return []

    seen_keys: set[str] = set()
    deduped: list[Event] = []

    for event in events:
        key = normalize_for_dedup(event)
        if key in seen_keys:
            continue

        is_duplicate = False
        event_venue_norm = normalize_venue(event.venue)
        for existing in deduped:
            if event.date.date() != existing.date.date():
                continue

            artist_ratio = fuzz.ratio(
                (event.artist or "").lower(), (existing.artist or "").lower()
            )
            existing_venue_norm = normalize_venue(existing.venue)

            # If both resolve to same canonical venue, it's a match
            if event_venue_norm == existing_venue_norm and artist_ratio > 85:
                is_duplicate = True
                break

            # Otherwise fall back to fuzzy venue matching
            venue_ratio = fuzz.ratio(event_venue_norm, existing_venue_norm)
            if artist_ratio > 85 and venue_ratio > 80:
                is_duplicate = True
                break

        if not is_duplicate:
            seen_keys.add(key)
            deduped.append(event)

    return deduped


def llm_dedup(events: list[Event]) -> list[Event]:
    """Use LLM to identify remaining duplicates."""
    # TODO: Implement LLM deduplication with Gemini (gemini-2.5-flash-lite)
    return events
