"""
Authentication Module
Handles user management, password hashing, and JWT token management
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
import asyncpg

from database_config import get_connection, execute, fetch, fetchrow, fetchval

# Password hashing configuration (Argon2)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


class User(BaseModel):
    """User model for API responses"""

    id: int
    username: str
    full_name: str
    email: str
    is_active: bool = True


class UserInDB(User):
    """User model with password hash (internal use)"""

    password_hash: str


class TokenData(BaseModel):
    """Token payload data"""

    user_id: Optional[int] = None


async def init_users_table():
    """Initialize the users table in the database"""
    await execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_email_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)


def hash_password(password: str) -> str:
    """Hash a password using Argon2"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    row = await fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    return dict(row) if row else None


async def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    row = await fetchrow("SELECT * FROM users WHERE username = $1", username)
    return dict(row) if row else None


async def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    row = await fetchrow("SELECT * FROM users WHERE email = $1", email)
    return dict(row) if row else None


async def create_user(username: str, full_name: str, email: str, password: str) -> int:
    """
    Create a new user.
    Returns the user ID on success.
    Raises ValueError if username or email already exists.
    """
    try:
        password_hash = hash_password(password)
        user_id = await fetchval(
            """
            INSERT INTO users (username, full_name, email, password_hash)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            username, full_name, email, password_hash
        )
        return user_id

    except asyncpg.UniqueViolationError as e:
        error_str = str(e).lower()
        if "username" in error_str:
            raise ValueError(f"Username '{username}' already exists")
        elif "email" in error_str:
            raise ValueError(f"Email '{email}' already registered")
        else:
            raise ValueError("User already exists")


async def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate a user by username and password.
    Returns user dict if valid, None otherwise.
    """
    user = await get_user_by_username(username)
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    if not user.get("is_active", True):
        return None

    return user


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for a user.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode = {"sub": str(user_id), "exp": expire, "iat": datetime.utcnow()}

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.
    Returns TokenData if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return TokenData(user_id=int(user_id))
    except JWTError:
        return None


async def update_password(user_id: int, old_password: str, new_password: str) -> bool:
    """
    Update a user's password.
    Returns True on success, raises ValueError if old password is incorrect.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found")

    if not verify_password(old_password, user["password_hash"]):
        raise ValueError("Current password is incorrect")

    new_hash = hash_password(new_password)
    result = await execute(
        """
        UPDATE users 
        SET password_hash = $1, updated_at = NOW()
        WHERE id = $2
        """,
        new_hash, user_id
    )
    return "UPDATE" in result


async def search_users(query: str, limit: int = 10) -> list:
    """
    Search users by username or email.
    Returns list of user dicts (without password hash).
    """
    search_pattern = f"%{query}%"
    rows = await fetch(
        """
        SELECT id, username, full_name, email, is_active
        FROM users
        WHERE (username ILIKE $1 OR email ILIKE $1 OR full_name ILIKE $1)
        AND is_active = TRUE
        LIMIT $2
        """,
        search_pattern, limit
    )
    return [dict(row) for row in rows]


async def deactivate_user(user_id: int) -> bool:
    """Deactivate a user account"""
    result = await execute(
        """
        UPDATE users 
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1
        """,
        user_id
    )
    return "UPDATE" in result
