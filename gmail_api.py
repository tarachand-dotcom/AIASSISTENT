"""
Gmail API integration for fetching recent emails (OPTIMIZED)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

ERROR_CREDENTIALS_MISSING = "credentials_missing"
ERROR_GMAIL_UNAVAILABLE = "gmail_unavailable"


# ================= AUTH =================

def credentials_file_exists() -> bool:
    return os.path.isfile(CREDENTIALS_FILE)


def authenticate_gmail() -> Dict[str, Any]:
    creds: Optional[Credentials] = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            return {"service": None, "error": ERROR_GMAIL_UNAVAILABLE}

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                return {"service": None, "error": ERROR_GMAIL_UNAVAILABLE}
        else:
            if not credentials_file_exists():
                return {"service": None, "error": ERROR_CREDENTIALS_MISSING}
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception:
                return {"service": None, "error": ERROR_GMAIL_UNAVAILABLE}

        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
        except OSError:
            return {"service": None, "error": ERROR_GMAIL_UNAVAILABLE}

    try:
        return {"service": build("gmail", "v1", credentials=creds), "error": None}
    except Exception:
        return {"service": None, "error": ERROR_GMAIL_UNAVAILABLE}


# ================= FAST EMAIL FETCH =================

def get_latest_emails(n: int = 5) -> Dict[str, Any]:

    if not credentials_file_exists() and not os.path.exists(TOKEN_FILE):
        return {"emails": [], "error": ERROR_CREDENTIALS_MISSING}

    auth = authenticate_gmail()
    if auth.get("error"):
        return {"emails": [], "error": auth["error"]}

    service = auth.get("service")
    if service is None:
        return {"emails": [], "error": ERROR_GMAIL_UNAVAILABLE}

    try:
        print("📥 Fetching emails...")

        # ✅ ONLY ONE API CALL (FAST)
        response = service.users().messages().list(
            userId="me",
            maxResults=n,
            q="is:unread"
        ).execute()

        messages = response.get("messages", []) or []

        emails: List[Dict[str, str]] = []

        # ✅ NO MORE .get() CALL HERE (REMOVED SLOW PART)
        for msg in messages:
            emails.append({
                "id": msg.get("id"),
                "snippet": msg.get("snippet", "")
            })

        return {"emails": emails, "error": None}

    except HttpError:
        return {"emails": [], "error": ERROR_GMAIL_UNAVAILABLE}
    except Exception:
        return {"emails": [], "error": ERROR_GMAIL_UNAVAILABLE}