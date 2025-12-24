"""
Token Usage Module
Handles tracking and querying of LLM token consumption
"""

import sqlite3
from typing import Optional, Dict, List
import uuid

DB_PATH = "database.db"


def init_token_usage_table():
    """Initialize the token_usage table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create indexes for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_session 
        ON token_usage(session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_project 
        ON token_usage(project_id)
    """)

    conn.commit()
    conn.close()


def generate_message_id() -> str:
    """Generate a unique message ID"""
    return str(uuid.uuid4())


def log_token_usage(
    project_id: int,
    session_id: str,
    message_id: str,
    user_id: int,
    source: str,
    usage_metadata: Dict,
) -> bool:
    """
    Log token usage for an AI message.
    
    Args:
        project_id: Project ID
        session_id: Chat session/thread ID
        message_id: Unique message ID
        user_id: User ID
        source: 'chat' or 'metadata_generation'
        usage_metadata: Dict with input_tokens, output_tokens, total_tokens
    
    Returns:
        True if successful, False otherwise
    """
    if not usage_metadata:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Handle different key names for token counts
        prompt_tokens = usage_metadata.get("input_tokens", 0) or usage_metadata.get("prompt_tokens", 0)
        completion_tokens = usage_metadata.get("output_tokens", 0) or usage_metadata.get("completion_tokens", 0)
        total_tokens = usage_metadata.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

        cursor.execute(
            """
            INSERT INTO token_usage 
            (project_id, session_id, message_id, user_id, source, prompt_tokens, completion_tokens, total_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, session_id, message_id, user_id, source, prompt_tokens, completion_tokens, total_tokens),
        )

        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to log token usage: {e}")
        return False
    finally:
        conn.close()


def get_session_token_usage(session_id: str) -> Dict:
    """
    Get total token usage for a session.
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens, message_count,
        and current_session_tokens (total_tokens from the last AIMessage)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get aggregate totals
    cursor.execute(
        """
        SELECT 
            COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) as completion_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as message_count
        FROM token_usage
        WHERE session_id = ?
        """,
        (session_id,),
    )

    row = cursor.fetchone()
    
    # Get total_tokens from the last message (current session context size)
    cursor.execute(
        """
        SELECT total_tokens
        FROM token_usage
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session_id,),
    )
    
    last_message = cursor.fetchone()
    current_session_tokens = last_message[0] if last_message else 0
    
    conn.close()

    return {
        "session_id": session_id,
        "prompt_tokens": row[0],
        "completion_tokens": row[1],
        "total_tokens": row[2],
        "message_count": row[3],
        "current_session_tokens": current_session_tokens,
    }


def get_project_token_usage(project_id: int) -> Dict:
    """
    Get total token usage for a project (all sessions + metadata generation).
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens, 
        message_count, session_count, breakdown by source
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Overall totals
    cursor.execute(
        """
        SELECT 
            COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) as completion_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as message_count,
            COUNT(DISTINCT session_id) as session_count
        FROM token_usage
        WHERE project_id = ?
        """,
        (project_id,),
    )

    row = cursor.fetchone()

    # Breakdown by source
    cursor.execute(
        """
        SELECT 
            source,
            COALESCE(SUM(total_tokens), 0) as total_tokens
        FROM token_usage
        WHERE project_id = ?
        GROUP BY source
        """,
        (project_id,),
    )

    breakdown = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    return {
        "project_id": project_id,
        "prompt_tokens": row[0],
        "completion_tokens": row[1],
        "total_tokens": row[2],
        "message_count": row[3],
        "session_count": row[4],
        "breakdown": {
            "chat": breakdown.get("chat", 0),
            "metadata_generation": breakdown.get("metadata_generation", 0),
        },
    }


def get_session_messages(session_id: str, limit: int = 100) -> List[Dict]:
    """
    Get individual message token usage for a session.
    
    Returns:
        List of message usage records
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            message_id,
            source,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            created_at
        FROM token_usage
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (session_id, limit),
    )

    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return messages
