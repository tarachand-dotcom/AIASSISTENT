"""
SQLite database manager for tasks and events.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Dict, Iterator, List


DB_PATH = "assistant.db"
_DATABASE_BOOTSTRAPPED = False


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Reusable database connection with row access by column name.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables() -> None:
    """
    Create required tables if they do not exist.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    date TEXT,
                    time TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    date TEXT,
                    time TEXT
                )
                """
            )
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to initialize database: {exc}") from exc


def init_db() -> None:
    """
    Backward-compatible alias for table creation.
    """
    create_tables()


def initialize_database() -> None:
    """
    Ensure database file and tables are created at startup.
    This function is safe to call multiple times.
    """
    global _DATABASE_BOOTSTRAPPED
    if _DATABASE_BOOTSTRAPPED:
        return

    try:
        # Explicit startup connection to create assistant.db even with no writes.
        startup_conn = sqlite3.connect("assistant.db")
        startup_conn.close()
        print("[DB] Connection established to assistant.db")

        create_tables()
        print("Database initialized successfully")
        _DATABASE_BOOTSTRAPPED = True
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Log startup error without crashing app import.
        print(f"[DB] Initialization error: {exc}")


def create_task(task_name: str, date: str, time: str) -> int:
    """
    Insert a task and return inserted ID.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (task_name, date, time, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (task_name.strip(), date.strip(), time.strip()),
            )
            return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to create task: {exc}") from exc


def get_all_tasks() -> List[Dict[str, str]]:
    """
    Fetch all tasks ordered by newest first.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, task_name, date, time, status
                FROM tasks
                ORDER BY id DESC
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": str(row["id"]),
                    "task_name": row["task_name"] or "",
                    "date": row["date"] or "",
                    "time": row["time"] or "",
                    "status": row["status"] or "pending",
                }
                for row in rows
            ]
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to fetch tasks: {exc}") from exc


def complete_task(task_id: int) -> bool:
    """
    Mark a task as done.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'done'
                WHERE id = ?
                """,
                (task_id,),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to complete task: {exc}") from exc


def delete_task(task_id: int) -> bool:
    """
    Delete a task by ID.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to delete task: {exc}") from exc


def create_event(event_name: str, date: str, time: str) -> int:
    """
    Insert an event and return inserted ID.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (event_name, date, time)
                VALUES (?, ?, ?)
                """,
                (event_name.strip(), date.strip(), time.strip()),
            )
            return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to create event: {exc}") from exc


def get_all_events() -> List[Dict[str, str]]:
    """
    Fetch all events ordered by newest first.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, event_name, date, time
                FROM events
                ORDER BY id DESC
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": str(row["id"]),
                    "event_name": row["event_name"] or "",
                    "date": row["date"] or "",
                    "time": row["time"] or "",
                }
                for row in rows
            ]
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to fetch events: {exc}") from exc


# Automatic initialization on module import.
initialize_database()
