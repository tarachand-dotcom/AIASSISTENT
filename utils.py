"""
Utility helpers for JSON parsing and output normalization.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_RESPONSE: Dict[str, Any] = {
    "intent": "general_query",
    "response": "I could not fully process that. Please try again with more detail.",
    "task": {"name": "", "date": "", "time": ""},
    "email": {"summary": "", "actions": [], "priority": "unknown"},
    "event": {"name": "", "date": "", "time": ""},
}


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all required keys exist with safe defaults.
    """
    safe = dict(DEFAULT_RESPONSE)
    safe.update(payload or {})

    safe_task = {"name": "", "date": "", "time": ""}
    safe_task.update(safe.get("task", {}) or {})
    safe["task"] = safe_task

    safe_email = {"summary": "", "actions": [], "priority": "unknown"}
    safe_email.update(safe.get("email", {}) or {})
    if not isinstance(safe_email.get("actions"), list):
        safe_email["actions"] = [str(safe_email["actions"])]
    safe["email"] = safe_email

    safe_event = {"name": "", "date": "", "time": ""}
    safe_event.update(safe.get("event", {}) or {})
    safe["event"] = safe_event

    if safe.get("intent") not in {
        "task_creation",
        "email_summary",
        "schedule_event",
        "check_emails",
        "general_query",
    }:
        safe["intent"] = "general_query"

    safe["response"] = str(safe.get("response", "")).strip() or DEFAULT_RESPONSE["response"]
    return safe


def parse_json_response(raw_text: str) -> Dict[str, Any]:
    """
    Parse model output as JSON.
    Handles raw JSON or JSON wrapped in markdown code fences.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return dict(DEFAULT_RESPONSE)

    # Attempt direct parse first.
    try:
        return normalize_payload(json.loads(raw_text))
    except json.JSONDecodeError:
        pass

    # Extract fenced JSON, then parse.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fence_match:
        try:
            return normalize_payload(json.loads(fence_match.group(1)))
        except json.JSONDecodeError:
            pass

    # Extract first JSON object as best effort.
    obj_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if obj_match:
        try:
            return normalize_payload(json.loads(obj_match.group(1)))
        except json.JSONDecodeError:
            pass

    # Fall back to safe default with raw text as response.
    fallback = dict(DEFAULT_RESPONSE)
    fallback["response"] = raw_text[:500]
    return normalize_payload(fallback)


def parse_email_digest_response(raw_text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Parse LLM output for bundled email analysis into summary and task dicts.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return "No model output to parse.", []

    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    if parsed is None:
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        obj_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(1))
            except json.JSONDecodeError:
                parsed = None

    if not isinstance(parsed, dict):
        return "Could not parse email analysis JSON. Showing raw snippet:\n\n" + raw_text[:800], []

    summary = str(parsed.get("summary", "")).strip() or "No summary returned."
    tasks_raw = parsed.get("tasks", [])
    if not isinstance(tasks_raw, list):
        tasks_raw = []

    tasks: List[Dict[str, str]] = []
    for item in tasks_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        tasks.append(
            {
                "name": name,
                "date": str(item.get("date", "")).strip(),
                "time": str(item.get("time", "")).strip(),
            }
        )

    return summary, tasks
