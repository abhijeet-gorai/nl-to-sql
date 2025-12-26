"""
Token Usage Module
Handles tracking and querying of LLM token consumption
"""

from typing import Dict, List
import uuid

from database_config import get_connection, execute, fetch, fetchrow


async def init_token_usage_table():
    """Initialize the token_usage table"""
    async with get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Create indexes for common queries
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_session 
            ON token_usage(session_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_project 
            ON token_usage(project_id)
        """)


def generate_message_id() -> str:
    """Generate a unique message ID"""
    return str(uuid.uuid4())


async def log_token_usage(
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

    try:
        # Handle different key names for token counts
        prompt_tokens = usage_metadata.get("input_tokens", 0) or usage_metadata.get("prompt_tokens", 0)
        completion_tokens = usage_metadata.get("output_tokens", 0) or usage_metadata.get("completion_tokens", 0)
        total_tokens = usage_metadata.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

        await execute(
            """
            INSERT INTO token_usage 
            (project_id, session_id, message_id, user_id, source, prompt_tokens, completion_tokens, total_tokens)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            project_id, session_id, message_id, user_id, source, prompt_tokens, completion_tokens, total_tokens
        )

        return True
    except Exception as e:
        print(f"Failed to log token usage: {e}")
        return False


async def get_session_token_usage(session_id: str) -> Dict:
    """
    Get total token usage for a session.
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens, message_count,
        and current_session_tokens (total_tokens from the last AIMessage)
    """
    # Get aggregate totals
    row = await fetchrow(
        """
        SELECT 
            COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) as completion_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as message_count
        FROM token_usage
        WHERE session_id = $1
        """,
        session_id
    )
    
    # Get total_tokens from the last message (current session context size)
    last_message = await fetchrow(
        """
        SELECT total_tokens
        FROM token_usage
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        session_id
    )
    
    current_session_tokens = last_message["total_tokens"] if last_message else 0

    return {
        "session_id": session_id,
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "total_tokens": row["total_tokens"],
        "message_count": row["message_count"],
        "current_session_tokens": current_session_tokens,
    }


async def get_project_token_usage(project_id: int) -> Dict:
    """
    Get total token usage for a project (all sessions + metadata generation).
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens, 
        message_count, session_count, breakdown by source
    """
    # Overall totals
    row = await fetchrow(
        """
        SELECT 
            COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) as completion_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as message_count,
            COUNT(DISTINCT session_id) as session_count
        FROM token_usage
        WHERE project_id = $1
        """,
        project_id
    )

    # Breakdown by source
    breakdown_rows = await fetch(
        """
        SELECT 
            source,
            COALESCE(SUM(total_tokens), 0) as total_tokens
        FROM token_usage
        WHERE project_id = $1
        GROUP BY source
        """,
        project_id
    )

    breakdown = {r["source"]: r["total_tokens"] for r in breakdown_rows}

    return {
        "project_id": project_id,
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "total_tokens": row["total_tokens"],
        "message_count": row["message_count"],
        "session_count": row["session_count"],
        "breakdown": {
            "chat": breakdown.get("chat", 0),
            "metadata_generation": breakdown.get("metadata_generation", 0),
        },
    }


async def get_session_messages(session_id: str, limit: int = 100) -> List[Dict]:
    """
    Get individual message token usage for a session.
    
    Returns:
        List of message usage records
    """
    rows = await fetch(
        """
        SELECT 
            message_id,
            source,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            created_at
        FROM token_usage
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        session_id, limit
    )

    return [dict(row) for row in rows]
