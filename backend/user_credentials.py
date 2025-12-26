"""
User Credentials Module
Handles secure storage and retrieval of user-provided WatsonX credentials
"""

import os
import hashlib
from typing import Optional, Dict
from cryptography.fernet import Fernet, InvalidToken
import asyncpg

from database_config import get_connection, execute, fetchrow

# Encryption key from environment variable
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY")


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    if not ENCRYPTION_KEY:
        raise ValueError("CREDENTIAL_ENCRYPTION_KEY environment variable not set")
    return Fernet(ENCRYPTION_KEY.encode())


async def init_user_credentials_table():
    """Initialize the user_credentials table in the database."""
    async with get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_credentials (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                watsonx_api_key_encrypted TEXT NOT NULL,
                watsonx_project_id TEXT NOT NULL,
                watsonx_url TEXT NOT NULL,
                is_validated BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key using Fernet symmetric encryption."""
    fernet = _get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key using Fernet symmetric encryption."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(encrypted_key.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt API key - invalid or corrupted data")


def mask_api_key(api_key: str) -> str:
    """Mask API key for display (show only last 4 characters)."""
    if len(api_key) <= 4:
        return "****"
    return "*" * 8 + api_key[-4:]


async def save_credentials(
    user_id: int,
    api_key: str,
    project_id: str,
    url: str,
    is_validated: bool = False
) -> bool:
    """
    Save or update user credentials.
    API key is encrypted before storage.
    
    Returns True on success.
    """
    try:
        encrypted_key = encrypt_api_key(api_key)

        async with get_connection() as conn:
            # PostgreSQL UPSERT syntax
            await conn.execute(
                """
                INSERT INTO user_credentials 
                (user_id, watsonx_api_key_encrypted, watsonx_project_id, watsonx_url, is_validated, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    watsonx_api_key_encrypted = EXCLUDED.watsonx_api_key_encrypted,
                    watsonx_project_id = EXCLUDED.watsonx_project_id,
                    watsonx_url = EXCLUDED.watsonx_url,
                    is_validated = EXCLUDED.is_validated,
                    updated_at = NOW()
                """,
                user_id, encrypted_key, project_id, url, is_validated
            )

        return True
    except Exception as e:
        print(f"Failed to save credentials: {e}")
        return False


async def get_credentials(user_id: int) -> Optional[Dict]:
    """
    Get decrypted credentials for a user.
    Returns dict with watsonx_api_key, watsonx_project_id, watsonx_url.
    Returns None if user has no credentials.
    """
    row = await fetchrow(
        """
        SELECT watsonx_api_key_encrypted, watsonx_project_id, watsonx_url, is_validated
        FROM user_credentials
        WHERE user_id = $1
        """,
        user_id
    )

    if not row:
        return None

    try:
        decrypted_key = decrypt_api_key(row["watsonx_api_key_encrypted"])
        return {
            "watsonx_api_key": decrypted_key,
            "watsonx_project_id": row["watsonx_project_id"],
            "watsonx_url": row["watsonx_url"],
            "is_validated": bool(row["is_validated"]),
        }
    except ValueError:
        # Decryption failed - credentials may be corrupted
        return None


async def get_masked_credentials(user_id: int) -> Optional[Dict]:
    """
    Get credentials with masked API key (for frontend display).
    Returns None if user has no credentials.
    """
    row = await fetchrow(
        """
        SELECT watsonx_api_key_encrypted, watsonx_project_id, watsonx_url, is_validated
        FROM user_credentials
        WHERE user_id = $1
        """,
        user_id
    )

    if not row:
        return None

    try:
        decrypted_key = decrypt_api_key(row["watsonx_api_key_encrypted"])
        return {
            "has_credentials": True,
            "watsonx_api_key_masked": mask_api_key(decrypted_key),
            "watsonx_project_id": row["watsonx_project_id"],
            "watsonx_url": row["watsonx_url"],
            "is_validated": bool(row["is_validated"]),
        }
    except ValueError:
        return None


async def delete_credentials(user_id: int) -> bool:
    """
    Delete user's credentials.
    Returns True if credentials were deleted, False if none existed.
    """
    result = await execute(
        "DELETE FROM user_credentials WHERE user_id = $1",
        user_id
    )
    return "DELETE" in result


def validate_credentials(api_key: str, project_id: str, url: str) -> tuple[bool, str]:
    """
    Validate WatsonX credentials by attempting to create a client.
    
    Returns (is_valid, error_message).
    """
    try:
        from langchain_ibm import ChatWatsonx
        
        # Create a minimal ChatWatsonx instance to verify credentials
        llm = ChatWatsonx(
            model_id="openai/gpt-oss-120b",
            url=url,
            project_id=project_id,
            apikey=api_key,
            params={"temperature": 0, "max_tokens": 10},
        )
        
        # Try a simple invoke to verify the credentials work
        response = llm.invoke("Say 'ok'")
        return True, ""
        
    except Exception as e:
        error_msg = str(e)
        # Clean up error message for user
        if "401" in error_msg or "Unauthorized" in error_msg.lower():
            return False, "Invalid API key"
        elif "404" in error_msg or "not found" in error_msg.lower():
            return False, "Invalid project ID or URL"
        elif "connection" in error_msg.lower():
            return False, "Could not connect to WatsonX URL"
        else:
            return False, f"Validation failed: {error_msg[:100]}"


async def get_credentials_hash(user_id: int) -> Optional[str]:
    """
    Get a hash of user's credentials configuration.
    Used for cache invalidation detection.
    """
    creds = await get_credentials(user_id)
    if not creds:
        return None
    
    key = f"{creds['watsonx_url']}:{creds['watsonx_project_id']}"
    return hashlib.md5(key.encode()).hexdigest()
