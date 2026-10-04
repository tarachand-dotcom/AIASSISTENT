"""
Complete Streamlit frontend for the Intelligent Personal AI Assistant.
Unified workflow: Ollama LLM, Gmail, Google Calendar, SQLite, and chat UI.
ChatGPT-inspired layout: centered chat, minimal sidebar, optional tasks panel.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from calendar_api import create_event as gcal_create_event, get_upcoming_events
from gmail_api import get_latest_emails
from llm import (
    extract_events_from_email,
    extract_tasks_from_email,
    get_email_digest_response,
    get_llm_response,
)
from task_manager import (
    complete_task,
    create_event as db_create_event,
    create_task,
    delete_task,
    get_all_events,
    get_all_tasks,
    init_db,
)
from utils import parse_email_digest_response
from voice import listen


MAX_EMAIL_BODY_CHARS = 800

st.set_page_config(
    page_title="AI Assistant",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_style_css() -> None:
    """Light, minimal theme: centered content, soft background, chat polish."""
    st.markdown(
        """
        <style>
            /* App shell */
            .stApp {
                background: linear-gradient(165deg, #f6f7fb 0%, #eef0f5 45%, #f4f5f9 100%);
            }
            [data-testid="stHeader"] { background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #ffffff 0%, #f8f9fc 100%);
                border-right: 1px solid #e6e8ef;
            }
            [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

            section.main {
                padding-bottom: 2rem;
            }

            /* Chat messages: card feel; user vs assistant alignment */
            [data-testid="stChatMessage"] {
                border-radius: 14px;
                border: 1px solid #e8eaef;
                background: #ffffff;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                margin-bottom: 0.65rem;
                padding: 0.35rem 0.5rem;
            }
            [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
                line-height: 1.55;
            }
            /* User bubble toward right (Streamlit 1.33+ structure) */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
                margin-left: auto !important;
                margin-right: 0 !important;
                max-width: min(92%, 34rem);
                background: #f0f4ff;
                border-color: #dbe4ff;
            }
            /* Assistant toward left */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
                margin-right: auto !important;
                margin-left: 0 !important;
                max-width: min(95%, 40rem);
                background: #ffffff;
            }

            /* Chat input bar */
            [data-testid="stChatInput"] {
                border-radius: 14px !important;
                border: 1px solid #dfe3ec !important;
                background: #ffffff !important;
            }

            /* Sidebar title */
            .sidebar-brand {
                font-size: 1.15rem;
                font-weight: 700;
                letter-spacing: -0.02em;
                color: #111827;
                margin-bottom: 0.25rem;
            }
            .sidebar-sub {
                font-size: 0.8rem;
                color: #6b7280;
                margin-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def build_email_bundle_for_llm(emails: List[Dict[str, str]]) -> str:
    """
    Combine fetched emails into one string for the digest model.
    """
    blocks: List[str] = []
    for idx, email in enumerate(emails, start=1):
        subject = email.get("subject", "(No subject)")
        sender = email.get("from", "Unknown")
        date = email.get("date", "")
        body = _truncate(email.get("body", ""), MAX_EMAIL_BODY_CHARS)
        blocks.append(
            "\n".join(
                [
                    f"--- Email {idx} ---",
                    f"Subject: {subject}",
                    f"From: {sender}",
                    f"Date: {date}",
                    "Body:",
                    body or "(empty / truncated)",
                ]
            )
        )
    return "\n\n".join(blocks)


def _format_single_email_for_extraction(email: Dict[str, str]) -> str:
    """Build one message string for extract_tasks_from_email()."""
    body = _truncate(email.get("body", ""), MAX_EMAIL_BODY_CHARS)
    return "\n".join(
        [
            f"Subject: {email.get('subject', '(No subject)')}",
            f"From: {email.get('from', '')}",
            f"Date: {email.get('date', '')}",
            "",
            "Body:",
            body or "(empty)",
        ]
    )


def _task_dedupe_key(task_name: str, date: str, time: str) -> str:
    """Stable key for duplicate detection (name + date + time)."""
    normalized = " ".join(task_name.lower().strip().split())
    return f"{normalized}|{date.strip()}|{time.strip()}"


def _existing_pending_task_keys() -> set[str]:
    """Keys for pending tasks already in the database."""
    keys: set[str] = set()
    try:
        for row in get_all_tasks():
            if str(row.get("status", "")).strip().lower() == "done":
                continue
            keys.add(
                _task_dedupe_key(
                    str(row.get("task_name", "")),
                    str(row.get("date", "")),
                    str(row.get("time", "")),
                )
            )
    except RuntimeError:
        pass
    return keys


_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize_event_time_hhmm(time_str: str) -> Optional[str]:
    """Return '' if no time, HH:MM if valid, None if non-empty but invalid."""
    t = (time_str or "").strip()
    if not t:
        return ""
    t = t.replace(".", ":")
    match = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _validate_event_datetime(date_str: str, time_str: str) -> tuple[bool, str, str]:
    """Require YYYY-MM-DD; optional time must be HH:MM when present."""
    d = (date_str or "").strip()
    if not _DATE_ISO.match(d):
        return False, "", ""
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        return False, "", ""
    tnorm = _normalize_event_time_hhmm(time_str)
    if tnorm is None:
        return False, "", ""
    if tnorm:
        try:
            datetime.strptime(f"{d} {tnorm}", "%Y-%m-%d %H:%M")
        except ValueError:
            return False, "", ""
    return True, d, tnorm


def _event_dedupe_key(event_name: str, date: str, time: str) -> str:
    normalized = " ".join(event_name.lower().strip().split())
    return f"{normalized}|{date.strip()}|{time.strip()}"


def _existing_event_keys() -> set[str]:
    """Keys for events already stored locally."""
    keys: set[str] = set()
    try:
        for row in get_all_events():
            keys.add(
                _event_dedupe_key(
                    str(row.get("event_name", "")),
                    str(row.get("date", "")),
                    str(row.get("time", "")),
                )
            )
    except RuntimeError:
        pass
    return keys


def run_email_digest_from_emails(emails: List[Dict[str, str]]) -> str:
    """
    Summarize emails with the LLM, extract tasks and calendar events per message,
    save via create_task / db_create_event with deduplication, return markdown for chat.
    """
    if not emails:
        return "No recent emails were returned from Gmail."

    bundle = build_email_bundle_for_llm(emails)
    raw_digest = get_email_digest_response(bundle)
    summary, _ = parse_email_digest_response(raw_digest)

    existing_pending = _existing_pending_task_keys()
    batch_seen: set[str] = set()
    saved_rows: List[str] = []
    saved_count = 0
    skipped_count = 0

    for email in emails:
        chunk = _format_single_email_for_extraction(email)
        for item in extract_tasks_from_email(chunk):
            name = str(item.get("task_name", "")).strip()
            date = str(item.get("date", "")).strip()
            time = str(item.get("time", "")).strip()
            if not name:
                continue
            key = _task_dedupe_key(name, date, time)
            if key in batch_seen or key in existing_pending:
                skipped_count += 1
                continue
            batch_seen.add(key)
            existing_pending.add(key)
            create_task(name, date, time)
            saved_count += 1
            when = " ".join(part for part in (date, time) if part).strip() or "no date/time"
            saved_rows.append(f"- **{name}** — _{when}_")

    existing_events = _existing_event_keys()
    event_batch_seen: set[str] = set()
    event_saved_rows: List[str] = []
    ev_saved = 0
    ev_skipped_dup = 0
    ev_skipped_invalid = 0

    for email in emails:
        chunk = _format_single_email_for_extraction(email)
        for ev in extract_events_from_email(chunk):
            ename = str(ev.get("event_name", "")).strip()
            raw_date = str(ev.get("date", "")).strip()
            raw_time = str(ev.get("time", "")).strip()
            if not ename:
                continue
            ok, ndate, ntime = _validate_event_datetime(raw_date, raw_time)
            if not ok:
                ev_skipped_invalid += 1
                continue
            ev_key = _event_dedupe_key(ename, ndate, ntime)
            if ev_key in event_batch_seen or ev_key in existing_events:
                ev_skipped_dup += 1
                continue
            event_batch_seen.add(ev_key)
            existing_events.add(ev_key)
            try:
                db_create_event(ename, ndate, ntime)
            except RuntimeError:
                ev_skipped_invalid += 1
                existing_events.discard(ev_key)
                event_batch_seen.discard(ev_key)
                continue
            ev_saved += 1
            slot = " ".join(p for p in (ndate, ntime) if p).strip() or ndate
            event_saved_rows.append(f"- **{ename}** — _{slot}_")

    lines: List[str] = [f"### Summary\n{summary}", "\n### Auto-saved tasks"]
    if saved_rows:
        lines.append(
            f"_Added **{saved_count}** new task(s); skipped **{skipped_count}** duplicate(s)._"
        )
        lines.extend(saved_rows)
    elif skipped_count:
        lines.append(f"_No new tasks. **{skipped_count}** duplicate(s) skipped._")
    else:
        lines.append("_No actionable tasks detected._")

    lines.append("\n### Auto-saved calendar events (local DB)")
    if event_saved_rows:
        lines.append(
            f"_Successfully added **{ev_saved}** event(s). "
            f"Skipped **{ev_skipped_dup}** duplicate(s) and **{ev_skipped_invalid}** invalid row(s)._"
        )
        lines.extend(event_saved_rows)
    elif ev_skipped_dup or ev_skipped_invalid:
        lines.append(
            f"_No new events saved. Duplicates skipped: **{ev_skipped_dup}**; "
            f"invalid date/time: **{ev_skipped_invalid}**._"
        )
    else:
        lines.append("_No calendar events detected in these emails._")

    return "\n".join(lines)


def run_email_check_pipeline() -> Optional[str]:
    """
    Fetch latest emails, then digest. Returns None if Gmail is not available (caller shows st.error).
    """
    result = get_latest_emails(5)
    if result.get("error"):
        return None
    emails = result.get("emails") or []
    return run_email_digest_from_emails(emails)


def process_llm_payload(payload: Dict[str, Any]) -> str:
    """
    Process parsed LLM JSON payload and run intent actions.
    """
    intent = str(payload.get("intent", "general_query")).strip()

    if intent == "task_creation":
        task = payload.get("task", {}) if isinstance(payload.get("task"), dict) else {}
        task_name = str(task.get("name", "")).strip()
        task_date = str(task.get("date", "")).strip()
        task_time = str(task.get("time", "")).strip()
        if not task_name:
            return "I detected task creation, but task name is missing."
        create_task(task_name, task_date, task_time)
        return f"Task created: **{task_name}** ({task_date or 'No date'} {task_time or 'No time'})"

    if intent == "schedule_event":
        event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
        event_name = str(event.get("name", "")).strip() or "Untitled Event"
        event_date = str(event.get("date", "")).strip()
        event_time = str(event.get("time", "")).strip()
        if not event_date:
            return "I detected scheduling intent, but I need a **date** (YYYY-MM-DD) to create the calendar event."

        try:
            gcal_result = gcal_create_event(event_name, event_date, event_time)
            try:
                db_create_event(event_name, event_date, event_time)
            except RuntimeError:
                pass
            link = str(gcal_result.get("htmlLink", "")).strip()
            msg = (
                f"Event scheduled in Google Calendar: **{event_name}** "
                f"({event_date} {event_time or 'default time'})"
            )
            if link:
                msg += f"\n\n[Open in Google Calendar]({link})"
            return msg
        except RuntimeError as exc:
            try:
                db_create_event(event_name, event_date, event_time)
                return (
                    f"Could not write to Google Calendar ({exc}). "
                    f"Saved locally: **{event_name}** ({event_date} {event_time or ''})."
                )
            except RuntimeError as db_exc:
                return f"Could not schedule the event. {exc} | {db_exc}"

    if intent == "email_summary":
        email = payload.get("email", {}) if isinstance(payload.get("email"), dict) else {}
        summary = str(email.get("summary", "")).strip() or "No summary available."
        priority = str(email.get("priority", "unknown")).strip() or "unknown"
        actions = email.get("actions", [])
        if not isinstance(actions, list):
            actions = [str(actions)]
        action_lines = "\n".join([f"- {item}" for item in actions]) if actions else "- No actions found"
        return f"**Summary:** {summary}\n\n**Priority:** {priority}\n\n**Suggested actions:**\n{action_lines}"

    if intent == "check_emails":
        try:
            out = run_email_check_pipeline()
            return out if out is not None else ""
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    return str(payload.get("response", "How can I help you?"))


ChatMessage = Tuple[str, str]
Conversation = List[ChatMessage]


def initialize_chat_state() -> None:
    """Initialize chat-related session state keys."""
    if "conversations" not in st.session_state:
        st.session_state.conversations = []
    if "current_chat" not in st.session_state:
        st.session_state.current_chat = []
    if "last_spoken_text" not in st.session_state:
        st.session_state.last_spoken_text = ""
    if "pending_user_input" not in st.session_state:
        st.session_state.pending_user_input = ""
    if "calendar_events" not in st.session_state:
        st.session_state.calendar_events = []
    if "calendar_fetch_error" not in st.session_state:
        st.session_state.calendar_fetch_error = ""
    if "ui_show_tasks_panel" not in st.session_state:
        st.session_state.ui_show_tasks_panel = True
    if "gmail_flash_error" not in st.session_state:
        st.session_state.gmail_flash_error = False

    if "chat_history" in st.session_state and st.session_state.chat_history and not st.session_state.current_chat:
        converted: Conversation = []
        for msg in st.session_state.chat_history:
            role = str(msg.get("role", "")).strip()
            content = str(msg.get("content", "")).strip()
            if role and content:
                converted.append((role, content))
        st.session_state.current_chat = converted
        st.session_state.chat_history = []


def save_current_chat_to_recents() -> None:
    """Save current chat as a completed conversation in recents."""
    current_chat: Conversation = st.session_state.current_chat
    if not current_chat:
        return

    snapshot = list(current_chat)
    conversations: List[Conversation] = st.session_state.conversations
    if conversations and conversations[-1] == snapshot:
        return
    conversations.append(snapshot)


def get_conversation_title(chat: Conversation, idx: int) -> str:
    """Build short label for the recents sidebar list."""
    for role, text in chat:
        if role == "user" and text.strip():
            preview = text.strip().replace("\n", " ")
            if len(preview) > 28:
                preview = f"{preview[:28]}..."
            return f"#{idx + 1}: {preview}"
    return f"#{idx + 1}"


def run_assistant(user_text: str) -> None:
    """Execute the assistant pipeline for one user message."""
    st.session_state.current_chat.append(("user", user_text))

    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            assistant_text = ""
            try:
                payload = get_llm_response(user_text)
                if isinstance(payload, dict) and str(payload.get("intent", "")).strip() == "check_emails":
                    with st.spinner("Fetching and analyzing emails..."):
                        assistant_text = run_email_check_pipeline()
                        if assistant_text is None:
                            st.error("Gmail not connected")
                            assistant_text = ""
                elif isinstance(payload, dict):
                    assistant_text = process_llm_payload(payload)
                else:
                    assistant_text = str(payload)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                assistant_text = f"Sorry, I ran into an issue. {exc}"

            if assistant_text and str(assistant_text).strip():
                st.markdown(assistant_text)

    st.session_state.current_chat.append(("assistant", assistant_text))


def render_tasks_panel_cards() -> None:
    """Tasks in bordered cards with Done / Delete."""
    st.markdown("### 📋 Tasks")
    try:
        tasks = get_all_tasks()
    except RuntimeError as exc:
        st.error(f"Failed to load tasks: {exc}")
        return

    if not tasks:
        with st.container(border=True):
            st.caption("No tasks yet. Chat or use **Check Emails** to add some.")
        return

    for task in tasks:
        task_id = int(task["id"])
        date_time = f"{task['date']} {task['time']}".strip() or "No date/time"
        status = str(task.get("status", "pending"))

        with st.container(border=True):
            st.markdown(f"**{task['task_name']}**")
            st.caption(f"🕐 {date_time} · **{status}**")
            b1, b2 = st.columns(2, gap="small")
            with b1:
                if status != "done" and st.button(
                    "✅ Done",
                    key=f"panel_task_done_{task_id}",
                    use_container_width=True,
                ):
                    try:
                        complete_task(task_id)
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))
            with b2:
                if st.button(
                    "❌ Delete",
                    key=f"panel_task_delete_{task_id}",
                    use_container_width=True,
                ):
                    try:
                        delete_task(task_id)
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))


def render_events_panel_cards() -> None:
    """Calendar + local events as clean cards."""
    st.markdown("---")
    st.markdown("### 📅 Events")

    err = str(st.session_state.get("calendar_fetch_error", "") or "").strip()
    if err:
        with st.container(border=True):
            st.warning(err)

    gcal_events = st.session_state.get("calendar_events") or []
    st.caption("Google Calendar")
    if not gcal_events:
        with st.container(border=True):
            st.caption("Use **View Schedule** in the sidebar to load upcoming events.")
    else:
        for ev in gcal_events:
            title = str(ev.get("summary", "(No title)"))
            start = str(ev.get("start", ""))
            link = str(ev.get("link", "")).strip()
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(start or "—")
                if link:
                    st.markdown(f"[Open in Calendar]({link})")

    st.markdown("---")
    st.caption("Local log")
    try:
        events = get_all_events()
    except RuntimeError as exc:
        st.error(f"Failed to load local events: {exc}")
        return

    if not events:
        with st.container(border=True):
            st.caption("No locally stored events.")
        return

    for event in events:
        date_time = f"{event['date']} {event['time']}".strip() or "No date/time"
        with st.container(border=True):
            st.markdown(f"**{event['event_name']}**")
            st.caption(date_time)


def render_sidebar() -> None:
    """Left sidebar: brand, primary actions, recents."""
    st.markdown('<p class="sidebar-brand">AI Assistant</p>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-sub">Chat · Gmail · Calendar · Tasks</p>', unsafe_allow_html=True)

    if st.button("🆕 New Chat", key="sidebar_nav_new_chat", use_container_width=True):
        save_current_chat_to_recents()
        st.session_state.current_chat = []
        st.session_state.last_spoken_text = ""
        st.session_state.pending_user_input = ""
        st.rerun()

    if st.button("📧 Check Emails", key="sidebar_nav_check_emails", use_container_width=True):
        fetch = get_latest_emails(5)
        if fetch.get("error"):
            st.session_state.gmail_flash_error = True
        else:
            st.session_state.current_chat.append(("user", "📧 Check Emails"))
            try:
                with st.spinner("Fetching and analyzing emails..."):
                    digest = run_email_digest_from_emails(fetch.get("emails") or [])
                st.session_state.current_chat.append(("assistant", digest))
            except Exception:  # pylint: disable=broad-exception-caught
                st.session_state.gmail_flash_error = True
        st.rerun()

    if st.button("📅 View Schedule", key="sidebar_nav_view_schedule", use_container_width=True):
        try:
            st.session_state.calendar_events = get_upcoming_events(10)
            st.session_state.calendar_fetch_error = ""
        except RuntimeError as exc:
            st.session_state.calendar_events = []
            st.session_state.calendar_fetch_error = str(exc)
        st.rerun()

    if st.button("📋 View Tasks", key="sidebar_nav_view_tasks", use_container_width=True):
        st.session_state.ui_show_tasks_panel = True
        st.rerun()

    st.markdown("---")

    with st.expander("🎙️ Voice input", expanded=False):
        if st.button("Listen now", key="sidebar_voice_listen_btn", use_container_width=True):
            try:
                spoken_text = listen()
                if spoken_text.strip():
                    st.session_state.last_spoken_text = spoken_text.strip()
                    st.session_state.pending_user_input = spoken_text.strip()
                    st.rerun()
                else:
                    st.warning("No speech detected.")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                st.error(f"Voice error: {exc}")

    st.markdown("---")
    st.caption("Recent chats")
    if not st.session_state.conversations:
        st.caption("None yet — start a conversation.")
    else:
        for idx, chat in enumerate(reversed(st.session_state.conversations)):
            actual_idx = len(st.session_state.conversations) - 1 - idx
            chat_title = get_conversation_title(chat, actual_idx)
            if st.button(
                chat_title,
                key=f"sidebar_recent_conv_{actual_idx}",
                use_container_width=True,
            ):
                st.session_state.current_chat = list(st.session_state.conversations[actual_idx])
                st.rerun()

    st.markdown("---")
    if st.session_state.get("ui_show_tasks_panel", True):
        if st.button("⏏️ Hide tasks panel", key="sidebar_toggle_hide_tasks", use_container_width=True):
            st.session_state.ui_show_tasks_panel = False
            st.rerun()
    else:
        if st.button("📋 Show tasks panel", key="sidebar_toggle_show_tasks", use_container_width=True):
            st.session_state.ui_show_tasks_panel = True
            st.rerun()


def render_main_chat() -> None:
    """Centered chat stream + input."""
    st.markdown("#### Chat")
    st.caption("Messages stay in this session until you start a **New Chat**.")

    for role, content in st.session_state.current_chat:
        with st.chat_message(role):
            if content and str(content).strip():
                st.markdown(content)

    if st.session_state.last_spoken_text:
        st.caption(f"Last voice: _{st.session_state.last_spoken_text}_")

    typed_input = st.chat_input("Message your assistant…")

    user_input = ""
    if st.session_state.pending_user_input:
        user_input = st.session_state.pending_user_input
        st.session_state.pending_user_input = ""
    elif typed_input:
        user_input = typed_input

    if user_input:
        run_assistant(user_input)


def main() -> None:
    """Application entrypoint."""
    init_db()
    initialize_chat_state()
    inject_style_css()

    with st.sidebar:
        render_sidebar()

    show_panel = bool(st.session_state.get("ui_show_tasks_panel", True))

    if show_panel:
        main_slot, panel_slot = st.columns([2.15, 1], gap="large")
    else:
        _sp_left, main_slot, _sp_right = st.columns([0.12, 2.6, 0.12], gap="medium")
        panel_slot = None

    with main_slot:
        if st.session_state.pop("gmail_flash_error", False):
            st.error("Gmail not connected")
        render_main_chat()

    if panel_slot is not None:
        with panel_slot:
            with st.container():
                st.markdown("##### Side panel")
                st.caption("Tasks & events")
                render_tasks_panel_cards()
                render_events_panel_cards()


if __name__ == "__main__":
    main()
