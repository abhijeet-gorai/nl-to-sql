"""
Database Configuration Module
Centralized PostgreSQL connection management with async connection pooling using asyncpg
"""

import os
from contextlib import asynccontextmanager
import asyncpg
from typing import Optional

# PostgreSQL Configuration from environment
PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "database": os.getenv("PGDATABASE", "nl_to_sql"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
    "ssl": os.getenv("PGSSLMODE", "prefer"),
}


def get_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    sslmode = os.getenv("PGSSLMODE", "prefer")
    return (
        f"postgresql://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
        f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}"
        f"?sslmode={sslmode}"
    )


# Async connection pool (initialized lazily)
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the async connection pool."""
    global _pool
    if _pool is None:
        ssl_mode = PG_CONFIG.get("ssl", "prefer")
        ssl = ssl_mode in ("require", "verify-ca", "verify-full")
        
        _pool = await asyncpg.create_pool(
            host=PG_CONFIG["host"],
            port=PG_CONFIG["port"],
            database=PG_CONFIG["database"],
            user=PG_CONFIG["user"],
            password=PG_CONFIG["password"],
            ssl=ssl if ssl else None,
            min_size=2,
            max_size=10,
        )
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a connection from the pool with automatic cleanup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_transaction():
    """Get a connection with a transaction."""
    async with get_connection() as conn:
        async with conn.transaction():
            yield conn


async def execute(query: str, *args):
    """Execute a query that doesn't return results."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list:
    """Execute a query and fetch all results as list of Records."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    """Execute a query and fetch a single row."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Execute a query and fetch a single value."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)


async def close_pool():
    """Close the connection pool (call on application shutdown)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
