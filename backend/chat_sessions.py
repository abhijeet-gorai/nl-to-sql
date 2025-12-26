"""
Chat Sessions Module
Handles persistence of chat sessions for history feature
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
import asyncpg

import agent  # Import for title generation

from database_config import get_connection, execute, fetch, fetchrow, fetchval

# India Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


async def init_chat_sessions_table():
    """Initialize the chat_sessions table in the database."""
    async with get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                thread_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                title TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        # Index for faster project lookups
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_project
            ON chat_sessions(project_id)
        """)


async def create_or_update_session(
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
    # Check if thread_id exists
    existing = await fetchrow(
        "SELECT id FROM chat_sessions WHERE thread_id = $1", thread_id
    )

    if existing:
        # Thread exists - just update timestamp
        await execute(
            "UPDATE chat_sessions SET updated_at = NOW() WHERE thread_id = $1",
            thread_id
        )
        return existing["id"]
    else:
        # New thread - generate title and insert
        title = "New Chat"
        if user_message:
            try:
                title = await agent.generate_chat_title(user_message, user_id)
            except Exception as e:
                print(f"Error generating title: {e}")
                # Fallback to simple truncation
                title = user_message[:47] + "..." if len(user_message) > 50 else user_message

        session_id = await fetchval(
            """
            INSERT INTO chat_sessions (project_id, thread_id, user_id, title)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            project_id, thread_id, user_id, title
        )
        return session_id


def _convert_to_ist(dt) -> str:
    """Convert timestamp to IST string."""
    if not dt:
        return None
    try:
        # PostgreSQL returns datetime with timezone info
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Convert to IST
            dt_ist = dt.astimezone(IST)
            return dt_ist.isoformat()
        # If it's already a string, parse it
        elif isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace(' ', 'T'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_ist = dt.astimezone(IST)
            return dt_ist.isoformat()
        return str(dt)
    except Exception:
        return str(dt) if dt else None


async def get_project_sessions(project_id: int) -> List[Dict]:
    """
    Get all chat sessions for a project, ordered by most recent.
    """
    rows = await fetch(
        """
        SELECT id, project_id, thread_id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE project_id = $1
        ORDER BY updated_at DESC
        """,
        project_id
    )

    sessions = []
    for row in rows:
        session = dict(row)
        session["created_at"] = _convert_to_ist(session["created_at"])
        session["updated_at"] = _convert_to_ist(session["updated_at"])
        sessions.append(session)
    
    return sessions


async def get_session(thread_id: str) -> Optional[Dict]:
    """
    Get a single session by thread_id.
    Returns timestamps in IST timezone.
    """
    row = await fetchrow(
        """
        SELECT id, project_id, thread_id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE thread_id = $1
        """,
        thread_id
    )

    if row:
        session = dict(row)
        session["created_at"] = _convert_to_ist(session["created_at"])
        session["updated_at"] = _convert_to_ist(session["updated_at"])
        return session
    return None


async def delete_session(thread_id: str) -> bool:
    """
    Delete a session by thread_id.
    Returns True if deleted, False if not found.
    """
    result = await execute(
        "DELETE FROM chat_sessions WHERE thread_id = $1", thread_id
    )
    return "DELETE" in result
