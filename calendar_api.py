"""
Google Calendar API integration for scheduling and viewing events.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar"
]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token_calendar.json"


def authenticate_calendar():
    """
    Authenticate and return an authorized Google Calendar service.
    """
    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise RuntimeError(
                    "Missing credentials.json. Add it to the project root after enabling Google Calendar API."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _build_event_times(date: str, time: str) -> Dict[str, str]:
    """
    Build RFC3339 start/end datetime strings for a 1-hour event.
    """
    if not date.strip():
        raise RuntimeError("Event date is required in YYYY-MM-DD format.")
    event_time = time.strip() or "09:00"

    try:
        start_naive = datetime.fromisoformat(f"{date}T{event_time}:00")
    except ValueError as exc:
        raise RuntimeError("Invalid date/time format. Use date=YYYY-MM-DD and time=HH:MM.") from exc

    local_tz = datetime.now().astimezone().tzinfo
    start_local = start_naive.replace(tzinfo=local_tz)
    end_local = start_local + timedelta(hours=1)
    return {"start": start_local.isoformat(), "end": end_local.isoformat()}


def _has_conflict(service, start_iso: str, end_iso: str) -> bool:
    """
    Basic conflict check for overlapping events in primary calendar.
    """
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy="startTime",
            maxResults=1,
        )
        .execute()
    )
    items = events_result.get("items", [])
    return len(items) > 0


def create_event(event_name: str, date: str, time: str) -> Dict[str, str]:
    """
    Create a Google Calendar event if no conflict exists.
    """
    try:
        service = authenticate_calendar()
        name = event_name.strip() or "Untitled Event"
        times = _build_event_times(date, time)

        if _has_conflict(service, times["start"], times["end"]):
            raise RuntimeError("Scheduling conflict detected in the selected time slot.")

        event_body = {
            "summary": name,
            "start": {"dateTime": times["start"]},
            "end": {"dateTime": times["end"]},
        }
        created = service.events().insert(calendarId="primary", body=event_body).execute()
        return {
            "id": created.get("id", ""),
            "htmlLink": created.get("htmlLink", ""),
            "start": times["start"],
            "end": times["end"],
        }
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar API error: {exc}") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to create calendar event: {exc}") from exc


def get_upcoming_events(max_results: int = 10) -> List[Dict[str, str]]:
    """
    Return upcoming events from primary calendar.
    """
    try:
        service = authenticate_calendar()
        now = datetime.utcnow().isoformat() + "Z"
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = events_result.get("items", [])
        upcoming: List[Dict[str, str]] = []
        for event in items:
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
            upcoming.append(
                {
                    "id": event.get("id", ""),
                    "summary": event.get("summary", "(No title)"),
                    "start": start,
                    "link": event.get("htmlLink", ""),
                }
            )
        return upcoming
    except HttpError as exc:
        raise RuntimeError(f"Google Calendar API error: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch upcoming events: {exc}") from exc
