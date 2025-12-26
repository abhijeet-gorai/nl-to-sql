"""
Authentication Module
Handles user management, password hashing, and JWT token management
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

# Database path
DB_PATH = "database.db"

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


def init_users_table():
    """Initialize the users table in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            is_email_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Hash a password using Argon2"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def create_user(username: str, full_name: str, email: str, password: str) -> int:
    """
    Create a new user.
    Returns the user ID on success.
    Raises ValueError if username or email already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        password_hash = hash_password(password)

        cursor.execute(
            """
            INSERT INTO users (username, full_name, email, password_hash)
            VALUES (?, ?, ?, ?)
        """,
            (username, full_name, email, password_hash),
        )

        conn.commit()
        user_id = cursor.lastrowid
        return user_id

    except sqlite3.IntegrityError as e:
        if "username" in str(e).lower():
            raise ValueError(f"Username '{username}' already exists")
        elif "email" in str(e).lower():
            raise ValueError(f"Email '{email}' already registered")
        else:
            raise ValueError("User already exists")
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate a user by username and password.
    Returns user dict if valid, None otherwise.
    """
    user = get_user_by_username(username)
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


def update_password(user_id: int, old_password: str, new_password: str) -> bool:
    """
    Update a user's password.
    Returns True on success, raises ValueError if old password is incorrect.
    """
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found")

    if not verify_password(old_password, user["password_hash"]):
        raise ValueError("Current password is incorrect")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        new_hash = hash_password(new_password)
        cursor.execute(
            """
            UPDATE users 
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (new_hash, user_id),
        )

        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def search_users(query: str, limit: int = 10) -> list:
    """
    Search users by username or email.
    Returns list of user dicts (without password hash).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    search_pattern = f"%{query}%"
    cursor.execute(
        """
        SELECT id, username, full_name, email, is_active
        FROM users
        WHERE (username LIKE ? OR email LIKE ? OR full_name LIKE ?)
        AND is_active = 1
        LIMIT ?
    """,
        (search_pattern, search_pattern, search_pattern, limit),
    )

    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return users


def deactivate_user(user_id: int) -> bool:
    """Deactivate a user account"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE users 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (user_id,),
        )

        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
