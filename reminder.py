"""
Background reminder notifier for tasks and events.

Run with:
    python reminder.py
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple

from plyer import notification


DB_PATH = "assistant.db"
CHECK_INTERVAL_SECONDS = 60

# Track notifications sent during current process runtime to avoid duplicates.
# Key format: (kind, row_id, date, time)
notified_items: Set[Tuple[str, int, str, str]] = set()


def get_connection() -> sqlite3.Connection:
    """
    Create SQLite connection with row access by column name.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_pending_tasks() -> List[Dict[str, str]]:
    """
    Fetch pending tasks from database.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, task_name, date, time
                FROM tasks
                WHERE status = 'pending'
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": int(row["id"]),
                    "task_name": (row["task_name"] or "").strip(),
                    "date": (row["date"] or "").strip(),
                    "time": (row["time"] or "").strip(),
                }
                for row in rows
            ]
    except sqlite3.Error as exc:
        print(f"[Reminder] Failed to fetch tasks: {exc}")
        return []


def fetch_events() -> List[Dict[str, str]]:
    """
    Fetch all events from database.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, event_name, date, time
                FROM events
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": int(row["id"]),
                    "event_name": (row["event_name"] or "").strip(),
                    "date": (row["date"] or "").strip(),
                    "time": (row["time"] or "").strip(),
                }
                for row in rows
            ]
    except sqlite3.Error as exc:
        print(f"[Reminder] Failed to fetch events: {exc}")
        return []


def send_notification(message: str) -> None:
    """
    Send desktop reminder notification.
    """
    try:
        notification.notify(
            title="Reminder",
            message=message,
            timeout=10,
            app_name="Personal AI Assistant",
        )
        print(f"[Reminder] Notification sent: {message}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[Reminder] Notification error: {exc}")


def check_due_items() -> None:
    """
    Check for due tasks/events and notify once per item.
    """
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")
    print(f"[Reminder] Checking reminders at {current_date} {current_time}")

    tasks = fetch_pending_tasks()
    events = fetch_events()

    if not tasks and not events:
        print("[Reminder] No tasks or events found.")
        return

    for task in tasks:
        task_time = task.get("time", "")
        task_date = task.get("date", "")
        task_id = int(task.get("id", 0))
        task_name = task.get("task_name", "Untitled Task")

        # If date is provided, only notify on that date.
        date_ok = (not task_date) or (task_date == current_date)
        key = ("task", task_id, task_date, task_time)
        if date_ok and task_time == current_time and key not in notified_items:
            send_notification(f"Task: {task_name}")
            notified_items.add(key)

    for event in events:
        event_time = event.get("time", "")
        event_date = event.get("date", "")
        event_id = int(event.get("id", 0))
        event_name = event.get("event_name", "Untitled Event")

        # If date is provided, only notify on that date.
        date_ok = (not event_date) or (event_date == current_date)
        key = ("event", event_id, event_date, event_time)
        if date_ok and event_time == current_time and key not in notified_items:
            send_notification(f"Event: {event_name}")
            notified_items.add(key)


def main() -> None:
    """
    Run reminder loop continuously in background.
    """
    print("[Reminder] Reminder service started.")
    print(f"[Reminder] Using database: {DB_PATH}")
    print(f"[Reminder] Checking every {CHECK_INTERVAL_SECONDS} seconds.")

    while True:
        try:
            check_due_items()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[Reminder] Unexpected error: {exc}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
