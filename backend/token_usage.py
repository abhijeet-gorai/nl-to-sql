"""
Token Usage Module
Handles tracking and querying of LLM token consumption
"""

from typing import Dict, List
import uuid
from datetime import datetime, timezone

from database_config import get_connection, execute, fetch, fetchrow

# Daily token limit for users using default API key (can be changed)
DEFAULT_API_DAILY_TOKEN_LIMIT = 50000


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
                api_source TEXT DEFAULT 'default',
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
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_user_daily 
            ON token_usage(user_id, api_source, created_at)
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
    api_source: str = "default",
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
        api_source: 'default' (env API key) or 'user' (user's own key)
    
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
            (project_id, session_id, message_id, user_id, source, api_source, prompt_tokens, completion_tokens, total_tokens)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            project_id, session_id, message_id, user_id, source, api_source, prompt_tokens, completion_tokens, total_tokens
        )

        return True
    except Exception as e:
        print(f"Failed to log token usage: {e}")
        return False


async def get_user_daily_usage(user_id: int, api_source: str = "default") -> Dict:
    """
    Get user's token usage for last 24 hours (using default API key).
    
    For 'chat' source: Only count the latest row per thread (current context size)
    For other sources: Sum all tokens
    
    Returns:
        Dict with total_tokens used in last 24 hours and remaining quota
    """
    # For chat source, we only want the latest row per session (current context size)
    # For other sources (metadata_generation), we sum all tokens
    row = await fetchrow(
        """
        WITH chat_latest AS (
            -- Get only the latest row per session for chat source
            SELECT DISTINCT ON (session_id) total_tokens
            FROM token_usage
            WHERE user_id = $1 
              AND api_source = $2
              AND source = 'chat'
              AND created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY session_id, created_at DESC
        ),
        other_sources AS (
            -- Sum all tokens for non-chat sources
            SELECT COALESCE(SUM(total_tokens), 0) as total_tokens
            FROM token_usage
            WHERE user_id = $1 
              AND api_source = $2
              AND source != 'chat'
              AND created_at >= NOW() - INTERVAL '24 hours'
        )
        SELECT 
            COALESCE((SELECT SUM(total_tokens) FROM chat_latest), 0) + 
            COALESCE((SELECT total_tokens FROM other_sources), 0) as tokens_used_24h
        """,
        user_id, api_source
    )
    
    tokens_used = row["tokens_used_24h"] if row else 0
    remaining = max(0, DEFAULT_API_DAILY_TOKEN_LIMIT - tokens_used)
    
    return {
        "tokens_used_24h": tokens_used,
        "daily_limit": DEFAULT_API_DAILY_TOKEN_LIMIT,
        "tokens_remaining": remaining,
        "limit_exceeded": tokens_used >= DEFAULT_API_DAILY_TOKEN_LIMIT,
    }


async def check_daily_limit(user_id: int, api_source: str = "default") -> tuple[bool, str]:
    """
    Check if user has exceeded their daily token limit.
    
    Args:
        user_id: User ID to check
        api_source: 'default' or 'user'
    
    Returns:
        (is_allowed, error_message) - True if allowed, False with message if exceeded
    """
    # No limit for users with their own API key
    if api_source == "user":
        return True, ""
    
    usage = await get_user_daily_usage(user_id, api_source)
    
    if usage["limit_exceeded"]:
        return False, f"Daily token limit of {DEFAULT_API_DAILY_TOKEN_LIMIT:,} tokens exceeded. Please add your own Groq API key in Settings to continue."
    
    return True, ""


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
