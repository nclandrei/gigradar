from dataclasses import dataclass
from datetime import datetime
from typing import Literal

DescriptionSource = Literal["scraped", "ai"]


@dataclass
class Event:
    title: str
    artist: str | None
    venue: str
    date: datetime
    url: str
    source: str
    category: Literal["music", "theatre", "culture"]
    price: str | None = None
    spotify_url: str | None = None
    # Enrichment fields for theatre/culture events
    description: str | None = None
    description_source: DescriptionSource | None = None
    image_url: str | None = None
    video_url: str | None = None
