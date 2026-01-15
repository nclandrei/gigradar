# GigRadar Design

**Date:** 2025-01-15

## Overview

GigRadar automatically scrapes event sources (venues, ticketing services, groups) weekly via GitHub Actions, matches music events against Spotify followed artists, and emails a digest of relevant upcoming events in Bucharest.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (weekly)                  │
├─────────────────────────────────────────────────────────────┤
│  1. Fetch Spotify followed artists                          │
│  2. Run scrapers (venues, ticketing, groups)                │
│  3. Filter events: Bucharest + followed artists             │
│  4. Deduplicate: exact match → Levenshtein → LLM            │
│  5. Compare against last week's results                     │
│  6. Send email via Resend with new events                   │
│  7. Save results to JSON, cleanup old files                 │
└─────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
gigradar/
├── scrapers/
│   ├── music/              # Filtered by Spotify artists
│   │   ├── iabilet.py
│   │   ├── control.py
│   │   ├── expirat.py
│   │   ├── quantic.py
│   │   └── jfr.py
│   └── theatre/            # Collected as-is, no filtering
│       └── bulandra.py
├── services/
│   ├── spotify.py          # Fetch followed artists
│   ├── dedup.py            # Exact + Levenshtein + LLM deduplication
│   ├── email.py            # Resend integration
│   └── http.py             # HTTP-first, Playwright fallback
├── scripts/
│   └── get_refresh_token.py  # One-time OAuth setup
├── data/                   # JSON results (date-prefixed)
├── main.py                 # Orchestrator
├── requirements.txt
└── .github/workflows/weekly.yml
```

## Data Model

```python
@dataclass
class Event:
    title: str
    artist: str | None        # None for theatre
    venue: str
    date: datetime
    url: str                  # Link to buy/info
    source: str               # e.g., "iabilet", "control"
    category: Literal["music", "theatre"]
    price: str | None         # Optional, free-form text
```

## Scraper Interface

Each scraper module implements:

```python
def scrape() -> list[Event]:
    """Fetch upcoming events from this source."""
    ...
```

HTTP-first approach with Playwright fallback for JS-heavy sites:

```python
def fetch_page(url: str, needs_js: bool = False) -> str:
    if needs_js:
        # Use Playwright
    else:
        # Use httpx
```

## Deduplication Pipeline

### Stage 1: Exact + Levenshtein Match

```python
def stage1_dedup(events: list[Event]) -> list[Event]:
    # Step A: Exact match (normalized artist + date + venue)
    
    # Step B: Fuzzy match remaining events
    # - Same date
    # - Levenshtein ratio > 0.85 on artist name
    # - Levenshtein ratio > 0.80 on venue name
    # Merge if both thresholds pass
```

Uses `rapidfuzz` library for performance.

### Stage 2: LLM Fuzzy Match

```python
def llm_dedup(events: list[Event]) -> list[Event]:
    # Send remaining events to GPT-4o-mini
    # Prompt: identify duplicates accounting for typos/title variations
    # Return merged list
```

Only runs on events that passed Stage 1 (cost control).

## Spotify Integration

### One-Time Setup

Run locally to get refresh token:

```bash
python scripts/get_refresh_token.py
# Opens browser → Spotify OAuth → prints refresh token
# Copy to GitHub secrets: SPOTIFY_REFRESH_TOKEN
```

Uses Authorization Code flow (refresh token never expires).

### Weekly Flow

```python
def get_followed_artists() -> list[str]:
    access_token = refresh_access_token(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        refresh_token=os.environ["SPOTIFY_REFRESH_TOKEN"],
    )
    # Paginate through /me/following?type=artist
    # Return list of artist names (normalized)
```

### Artist Matching

```python
def match_events(events: list[Event], artists: list[str]) -> list[Event]:
    artist_set = {normalize(a) for a in artists}
    
    matched = []
    for event in events:
        # Exact match first
        if normalize(event.artist) in artist_set:
            matched.append(event)
            continue
        
        # Fuzzy match (Levenshtein > 0.85)
        for artist in artist_set:
            if ratio(normalize(event.artist), artist) > 0.85:
                matched.append(event)
                break
    
    return matched
```

## Email Format

Via Resend API:

```
Subject: GigRadar Weekly - 3 concerts, 2 theatre shows

## 🎵 Music Events (matching your Spotify)

### Subcarpați @ Control
📅 Sat, Feb 15 · 💰 80 RON
🔗 iabilet.ro | control-club.ro

### Robin and the Backstabbers @ Expirat  
📅 Thu, Feb 20 · 💰 60 RON
🔗 iabilet.ro

---

## 🎭 Theatre

### Așteptându-l pe Godot @ Bulandra
📅 Fri, Feb 21 · 💰 50-120 RON
🔗 bulandra.ro
```

## GitHub Actions Workflow

```yaml
name: GigRadar Weekly
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday 9am UTC
  workflow_dispatch:       # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: playwright install chromium
      - run: python main.py
        env:
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          SPOTIFY_REFRESH_TOKEN: ${{ secrets.SPOTIFY_REFRESH_TOKEN }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

## JSON Storage

### File Naming

```
data/
├── 2025-01-13.json
├── 2025-01-06.json
└── ...
```

### Schema

```json
{
  "scraped_at": "2025-01-13T09:00:00Z",
  "music_events": [...],
  "theatre_events": [...],
  "spotify_artists": ["Artist1", "Artist2"]
}
```

### Cleanup

Files older than 7 days are deleted after each run.

### Diffing

Compare against previous week's JSON to only email **new** events.

## Required Secrets

| Secret | Purpose |
|--------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | Long-lived refresh token from OAuth |
| `RESEND_API_KEY` | Resend email API key |
| `GEMINI_API_KEY` | For LLM deduplication stage |

## Dependencies

- `httpx` - HTTP client
- `playwright` - JS rendering fallback
- `beautifulsoup4` - HTML parsing
- `rapidfuzz` - Levenshtein matching
- `google-genai` - LLM deduplication (gemini-2.5-flash-lite)
- `resend` - Email sending
