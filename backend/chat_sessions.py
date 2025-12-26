"""
Chat Sessions Module
Handles persistence of chat sessions for history feature
"""

import sqlite3
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta

import agent  # Import for title generation

DB_PATH = "database.db"

# India Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def init_chat_sessions_table():
    """Initialize the chat_sessions table in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            thread_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Index for faster project lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_project
        ON chat_sessions(project_id)
    """)

    conn.commit()
    conn.close()


def create_or_update_session(
    project_id: int,
    thread_id: str,
    user_id: int,
    user_message: str = None,
) -> int:
    """
    Create a new session or update existing one.
    If new session, generates title using LLM from user_message.
    If existing session, just updates timestamp.
    Returns the session ID.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if thread_id exists
        cursor.execute("SELECT id FROM chat_sessions WHERE thread_id = ?", (thread_id,))
        existing = cursor.fetchone()

        if existing:
            # Thread exists - just update timestamp
            cursor.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?",
                (thread_id,)
            )
            conn.commit()
            return existing[0]
        else:
            # New thread - generate title and insert
            title = "New Chat"
            if user_message:
                try:
                    title = agent.generate_chat_title(user_message, user_id)
                except Exception as e:
                    print(f"Error generating title: {e}")
                    # Fallback to simple truncation
                    title = user_message[:47] + "..." if len(user_message) > 50 else user_message

            cursor.execute(
                """
                INSERT INTO chat_sessions (project_id, thread_id, user_id, title)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, thread_id, user_id, title),
            )
            conn.commit()
            return cursor.lastrowid

    finally:
        conn.close()


def _convert_to_ist(dt_str: str) -> str:
    """Convert UTC timestamp string to IST."""
    if not dt_str:
        return None
    try:
        # Parse the timestamp (SQLite stores as UTC)
        dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Convert to IST
        dt_ist = dt.astimezone(IST)
        return dt_ist.isoformat()
    except Exception:
        return dt_str


def get_project_sessions(project_id: int) -> List[Dict]:
    """
    Get all chat sessions for a project, ordered by most recent.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, project_id, thread_id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE project_id = ?
        ORDER BY updated_at DESC
        """,
        (project_id,),
    )

    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        session["created_at"] = _convert_to_ist(session["created_at"])
        session["updated_at"] = _convert_to_ist(session["updated_at"])
        sessions.append(session)
    
    conn.close()
    return sessions


def get_session(thread_id: str) -> Optional[Dict]:
    """
    Get a single session by thread_id.
    Returns timestamps in IST timezone.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, project_id, thread_id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE thread_id = ?
        """,
        (thread_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        session = dict(row)
        session["created_at"] = _convert_to_ist(session["created_at"])
        session["updated_at"] = _convert_to_ist(session["updated_at"])
        return session
    return None


def delete_session(thread_id: str) -> bool:
    """
    Delete a session by thread_id.
    Returns True if deleted, False if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
