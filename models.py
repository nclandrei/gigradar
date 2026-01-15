from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class Event:
    title: str
    artist: str | None
    venue: str
    date: datetime
    url: str
    source: str
    category: Literal["music", "theatre"]
    price: str | None = None
