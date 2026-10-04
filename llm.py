"""
LLM interaction layer using Ollama.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from prompt import (
    EMAIL_DIGEST_SYSTEM_PROMPT,
    EMAIL_EVENT_EXTRACTION_PROMPT,
    EMAIL_TASK_EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
)
from utils import parse_json_response


MODEL_NAME = "llama3"


def get_llm_response(user_input: str) -> Dict[str, Any]:
    """
    Send user input to Ollama and return normalized structured JSON.
    """
    try:
        # Import lazily so missing dependency does not crash app startup.
        import ollama

        result = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            format="json",  # Requests JSON output when supported by the model.
        )
        raw_content = result.get("message", {}).get("content", "")
        return parse_json_response(raw_content)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Keep UI resilient if Ollama is unavailable or returns malformed data.
        return {
            "intent": "general_query",
            "response": f"LLM error: {exc}",
            "task": {"name": "", "date": "", "time": ""},
            "email": {"summary": "", "actions": [], "priority": "unknown"},
            "event": {"name": "", "date": "", "time": ""},
        }


def get_email_digest_response(combined_email_text: str) -> str:
    """
    Ask the model to summarize bundled emails and extract tasks; returns raw JSON/text for parsing.
    """
    try:
        import ollama

        result = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": EMAIL_DIGEST_SYSTEM_PROMPT},
                {"role": "user", "content": combined_email_text},
            ],
            format="json",
        )
        return str(result.get("message", {}).get("content", ""))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return json.dumps(
            {
                "summary": f"LLM error while analyzing emails: {exc}",
                "tasks": [],
            }
        )


def _parse_extract_tasks_payload(raw_text: str) -> List[Dict[str, str]]:
    """
    Parse JSON from extract_tasks_from_email model output into normalized dicts.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return []

    parsed: Any = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    if parsed is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if fence:
            try:
                parsed = json.loads(fence.group(1))
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        obj = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if obj:
            try:
                parsed = json.loads(obj.group(1))
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return []

    tasks_raw = parsed.get("tasks", [])
    if not isinstance(tasks_raw, list):
        return []

    out: List[Dict[str, str]] = []
    for item in tasks_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("task_name", "") or item.get("name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "task_name": name,
                "date": str(item.get("date", "") or "").strip(),
                "time": str(item.get("time", "") or "").strip(),
            }
        )
    return out


def extract_tasks_from_email(email_text: str) -> List[Dict[str, str]]:
    """
    Call the LLM to extract actionable tasks from email body text (or bundled emails).

    Returns a list of dicts with keys: task_name, date, time (empty strings when unknown).
    On failure, returns an empty list (never raises).
    """
    text = (email_text or "").strip()
    if not text:
        return []

    try:
        import ollama

        result = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": EMAIL_TASK_EXTRACTION_PROMPT},
                {"role": "user", "content": text},
            ],
            format="json",
        )
        raw = str(result.get("message", {}).get("content", ""))
        return _parse_extract_tasks_payload(raw)
    except Exception:  # pylint: disable=broad-exception-caught
        return []


def _parse_extract_events_payload(raw_text: str) -> List[Dict[str, str]]:
    """Parse JSON from extract_events_from_email model output."""
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return []

    parsed: Any = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    if parsed is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if fence:
            try:
                parsed = json.loads(fence.group(1))
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        obj = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if obj:
            try:
                parsed = json.loads(obj.group(1))
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return []

    events_raw = parsed.get("events", [])
    if not isinstance(events_raw, list):
        return []

    out: List[Dict[str, str]] = []
    for item in events_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("event_name", "") or item.get("name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "event_name": name,
                "date": str(item.get("date", "") or "").strip(),
                "time": str(item.get("time", "") or "").strip(),
            }
        )
    return out


def extract_events_from_email(email_text: str) -> List[Dict[str, str]]:
    """
    Call the LLM to extract calendar events from email text.

    Returns dicts with keys: event_name, date, time (empty time allowed).
    On failure, returns an empty list (never raises).
    """
    text = (email_text or "").strip()
    if not text:
        return []

    try:
        import ollama

        result = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": EMAIL_EVENT_EXTRACTION_PROMPT},
                {"role": "user", "content": text},
            ],
            format="json",
        )
        raw = str(result.get("message", {}).get("content", ""))
        return _parse_extract_events_payload(raw)
    except Exception:  # pylint: disable=broad-exception-caught
        return []
