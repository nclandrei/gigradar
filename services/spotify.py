import os

import httpx


def refresh_access_token() -> str:
    """Refresh the Spotify access token using the stored refresh token."""
    response = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
        },
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_followed_artists() -> list[str]:
    """Fetch all followed artists from Spotify."""
    access_token = refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    artists: list[str] = []
    url = "https://api.spotify.com/v1/me/following?type=artist&limit=50"

    while url:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        for artist in data["artists"]["items"]:
            artists.append(artist["name"])

        url = data["artists"].get("next")

    return artists


def normalize(name: str) -> str:
    """Normalize artist name for matching."""
    return name.lower().strip()
