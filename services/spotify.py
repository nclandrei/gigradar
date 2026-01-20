import os
import re

import httpx
from rapidfuzz import fuzz

_access_token_cache: dict[str, str] = {}

MATCH_THRESHOLD = 80  # Minimum fuzzy match score (0-100)


def get_access_token() -> str:
    """Get access token using Client Credentials flow (no user login needed)."""
    if "token" in _access_token_cache:
        return _access_token_cache["token"]
    
    response = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    _access_token_cache["token"] = token
    return token


def normalize(name: str) -> str:
    """Normalize artist name for matching."""
    name = name.lower().strip()
    # Remove country codes like [RO], [UK], (US)
    name = re.sub(r"\s*[\[\(][a-z]{2,3}(?:/[a-z]{2,3})?[\]\)]\s*", "", name, flags=re.IGNORECASE)
    # Remove common suffixes
    name = re.sub(r"\s*\(album launch\)", "", name, flags=re.IGNORECASE)
    return name.strip()


def split_artists(artist_string: str) -> list[str]:
    """Split a multi-artist string into individual artist names.
    
    Handles separators like ", ", " & ", " x ", " w/ ".
    """
    # Split on common separators
    parts = re.split(r"\s*,\s*|\s+&\s+|\s+x\s+|\s+w/\s+", artist_string)
    # Clean up each part and filter empties
    return [p.strip() for p in parts if p.strip()]


def _search_single_artist(artist_name: str, headers: dict) -> str | None:
    """Search for a single artist on Spotify."""
    query = normalize(artist_name)
    if not query:
        return None
    
    response = httpx.get(
        "https://api.spotify.com/v1/search",
        params={"q": query, "type": "artist", "limit": 1},
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()
    
    artists = data.get("artists", {}).get("items", [])
    if not artists:
        return None
    
    artist = artists[0]
    spotify_name = normalize(artist["name"])
    
    score = fuzz.ratio(query, spotify_name)
    if score < MATCH_THRESHOLD:
        return None
    
    return f"https://open.spotify.com/artist/{artist['id']}"


def search_artists(artist_string: str) -> list[str]:
    """Search for artists on Spotify and return their page URLs.
    
    Handles multi-artist strings by splitting and searching each.
    Only returns URLs for artists that match with score >= MATCH_THRESHOLD.
    """
    if not artist_string:
        return []
    
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    artists = split_artists(artist_string)
    urls = []
    
    for artist in artists:
        url = _search_single_artist(artist, headers)
        if url:
            urls.append(url)
    
    return urls


def search_artist(artist_name: str) -> str | None:
    """Search for an artist on Spotify and return their page URL if found.
    
    For multi-artist strings, returns the first matching artist's URL.
    Only returns a URL if the Spotify result matches the query with
    a fuzzy score >= MATCH_THRESHOLD.
    """
    urls = search_artists(artist_name)
    return urls[0] if urls else None
