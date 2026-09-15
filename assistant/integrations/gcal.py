"""Google Calendar — the source of truth for events.

The assistant reads freely and writes only what you have confirmed. Every write
path here is called from a confirmed proposal, never from parsing alone.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..config import Profile
from ..models import Event

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_service(
    token_path: str = "token.json", credentials_path: str = "credentials.json"
):
    """Authorised Calendar client. Run once interactively to mint token.json."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _to_event(raw: dict, profile: Profile) -> Event | None:
    """One Calendar API item as a domain Event. All-day items are skipped."""
    start_raw = raw.get("start", {}).get("dateTime")
    end_raw = raw.get("end", {}).get("dateTime")
    if not start_raw or not end_raw:
        return None  # all-day entries do not occupy hours

    attendees = tuple(
        a.get("email", "")
        for a in raw.get("attendees", [])
        if not a.get("self") and not a.get("resource")
    )
    location = raw.get("location")
    if not location and raw.get("hangoutLink"):
        location = "Google Meet"

    return Event(
        id=raw["id"],
        title=raw.get("summary", "(no title)"),
        start=profile.localize(datetime.fromisoformat(start_raw)),
        end=profile.localize(datetime.fromisoformat(end_raw)),
        location=location,
        attendees=attendees,
        source="gcal",
        external_id=raw["id"],
        # An event you own with nobody else on it is yours to move.
        movable=not attendees and raw.get("organizer", {}).get("self", False),
    )


def fetch_events(service, profile: Profile, day: date, days: int = 1) -> list[Event]:
    """Every timed event between `day` 00:00 and `day + days` 00:00."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=profile.tz)
    end = start + timedelta(days=days)
    raw = (
        service.events()
        .list(
            calendarId=profile.calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
        )
        .execute()
    )
    events = (_to_event(item, profile) for item in raw.get("items", []))
    return [e for e in events if e is not None and e.title != "(declined)"]


def create_event(service, profile: Profile, event: Event) -> str:
    body = {
        "summary": event.title,
        "start": {"dateTime": event.start.isoformat(), "timeZone": profile.timezone},
        "end": {"dateTime": event.end.isoformat(), "timeZone": profile.timezone},
    }
    if event.location:
        body["location"] = event.location
    if event.attendees:
        body["attendees"] = [{"email": a} for a in event.attendees if "@" in a]
    created = service.events().insert(calendarId=profile.calendar_id, body=body).execute()
    return created["id"]


def move_event(service, profile: Profile, event_id: str, new_start: datetime,
               duration_minutes: int) -> dict:
    """Shift an existing event. Only ever called from a confirmed proposal."""
    new_start = profile.localize(new_start)
    body = {
        "start": {"dateTime": new_start.isoformat(), "timeZone": profile.timezone},
        "end": {
            "dateTime": (new_start + timedelta(minutes=duration_minutes)).isoformat(),
            "timeZone": profile.timezone,
        },
    }
    return (
        service.events()
        .patch(calendarId=profile.calendar_id, eventId=event_id, body=body)
        .execute()
    )
