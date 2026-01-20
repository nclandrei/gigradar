import os

import httpx

_access_token_cache: dict[str, str] = {}


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


def search_artist(artist_name: str) -> str | None:
    """Search for an artist on Spotify and return their page URL if found."""
    if not artist_name:
        return None
    
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = httpx.get(
        "https://api.spotify.com/v1/search",
        params={"q": artist_name, "type": "artist", "limit": 1},
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()
    
    artists = data.get("artists", {}).get("items", [])
    if not artists:
        return None
    
    artist = artists[0]
    return f"https://open.spotify.com/artist/{artist['id']}"


def normalize(name: str) -> str:
    """Normalize artist name for matching."""
    return name.lower().strip()
