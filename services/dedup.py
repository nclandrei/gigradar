from rapidfuzz import fuzz

from models import Event


def normalize_for_dedup(event: Event) -> str:
    """Create a normalized key for exact deduplication."""
    artist = (event.artist or "").lower().strip()
    venue = event.venue.lower().strip()
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
        for existing in deduped:
            if event.date.date() != existing.date.date():
                continue

            artist_ratio = fuzz.ratio(
                (event.artist or "").lower(), (existing.artist or "").lower()
            )
            venue_ratio = fuzz.ratio(event.venue.lower(), existing.venue.lower())

            if artist_ratio > 85 and venue_ratio > 80:
                is_duplicate = True
                break

        if not is_duplicate:
            seen_keys.add(key)
            deduped.append(event)

    return deduped


def llm_dedup(events: list[Event]) -> list[Event]:
    """Use LLM to identify remaining duplicates."""
    # TODO: Implement LLM deduplication with OpenAI
    return events
