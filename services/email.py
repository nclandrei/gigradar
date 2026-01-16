import os

import resend

from models import Event


def format_event(event: Event) -> str:
    """Format a single event for the email."""
    date_str = event.date.strftime("%a, %b %d")
    price_str = f" · 💰 {event.price}" if event.price else ""
    return f"""### {event.title} @ {event.venue}
📅 {date_str}{price_str}
🔗 {event.url}
"""


def send_digest(
    music_events: list[Event],
    theatre_events: list[Event],
    culture_events: list[Event],
    to_email: str,
) -> None:
    """Send the weekly digest email via Resend."""
    resend.api_key = os.environ["RESEND_API_KEY"]

    music_count = len(music_events)
    theatre_count = len(theatre_events)
    culture_count = len(culture_events)
    subject = f"GigRadar Weekly - {music_count} concerts, {theatre_count} theatre, {culture_count} culture"

    body_parts: list[str] = []

    if music_events:
        body_parts.append("## 🎵 Music Events (matching your Spotify)\n")
        for event in music_events:
            body_parts.append(format_event(event))

    if music_events and theatre_events:
        body_parts.append("\n---\n")

    if theatre_events:
        body_parts.append("## 🎭 Theatre\n")
        for event in theatre_events:
            body_parts.append(format_event(event))

    if (music_events or theatre_events) and culture_events:
        body_parts.append("\n---\n")

    if culture_events:
        body_parts.append("## 🎨 Culture\n")
        for event in culture_events:
            body_parts.append(format_event(event))

    body = "\n".join(body_parts)

    resend.Emails.send(
        {
            "from": "GigRadar <gigradar@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
    )
