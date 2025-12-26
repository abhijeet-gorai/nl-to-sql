"""
Connection Manager Module
Manages database connections and credentials with encryption
"""

import json
from typing import Dict, List, Optional
from cryptography.fernet import Fernet
import os
import asyncpg

from db_connector import DatabaseConnector, ConnectionConfig, get_connector_class
from database_config import get_connection, get_transaction, execute, fetch, fetchrow, fetchval

# Get encryption key from environment
ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a key for development (in production, this should be set)
    ENCRYPTION_KEY = Fernet.generate_key()
    print(
        "WARNING: Using generated encryption key. Set DB_ENCRYPTION_KEY in production."
    )
    print(f"Generated key: {ENCRYPTION_KEY.decode()}")

cipher_suite = Fernet(
    ENCRYPTION_KEY if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY.encode()
)

CONNECTIONS_TABLE = "db_connections"
EXTERNAL_TABLES_TABLE = "external_tables"


async def init_connections_table():
    """Initialize the connections and external tables tables"""
    async with get_connection() as conn:
        # Create connections table
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {CONNECTIONS_TABLE} (
                id SERIAL PRIMARY KEY,
                connection_name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                host TEXT,
                port INTEGER,
                database_name TEXT,
                username TEXT,
                password_encrypted TEXT,
                ssl_enabled BOOLEAN DEFAULT FALSE,
                connection_params TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                project_id INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(connection_name, project_id)
            )
        """)

        # Create external tables table
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {EXTERNAL_TABLES_TABLE} (
                id SERIAL PRIMARY KEY,
                connection_id INTEGER NOT NULL,
                schema_name TEXT,
                table_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                columns_metadata TEXT,
                row_count INTEGER,
                last_synced TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                is_selected BOOLEAN DEFAULT FALSE,
                project_id INTEGER,
                FOREIGN KEY (connection_id) REFERENCES {CONNECTIONS_TABLE}(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(connection_id, schema_name, table_name)
            )
        """)

        # Add columns to app_metadata if they don't exist (PostgreSQL way)
        # Check and add source_type column
        await conn.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name = 'app_metadata' AND column_name = 'source_type') THEN
                    ALTER TABLE app_metadata ADD COLUMN source_type TEXT DEFAULT 'csv';
                END IF;
            END $$;
        """)

        # Check and add connection_id column
        await conn.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name = 'app_metadata' AND column_name = 'connection_id') THEN
                    ALTER TABLE app_metadata ADD COLUMN connection_id INTEGER;
                END IF;
            END $$;
        """)

        # Check and add schema_name column
        await conn.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name = 'app_metadata' AND column_name = 'schema_name') THEN
                    ALTER TABLE app_metadata ADD COLUMN schema_name TEXT;
                END IF;
            END $$;
        """)


def encrypt_password(password: str) -> str:
    """Encrypt password using Fernet symmetric encryption"""
    return cipher_suite.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt password"""
    return cipher_suite.decrypt(encrypted.encode()).decode()


async def create_connection(connection_data: Dict, project_id: int = None) -> int:
    """Create new database connection"""
    try:
        # Encrypt password
        encrypted_pwd = encrypt_password(connection_data["password"])

        connection_id = await fetchval(
            f"""
            INSERT INTO {CONNECTIONS_TABLE} 
            (connection_name, db_type, host, port, database_name, username, 
             password_encrypted, ssl_enabled, connection_params, project_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            connection_data["connection_name"],
            connection_data["db_type"],
            connection_data.get("host"),
            connection_data.get("port"),
            connection_data.get("database_name"),
            connection_data.get("username"),
            encrypted_pwd,
            connection_data.get("ssl_enabled", False),
            json.dumps(connection_data.get("connection_params", {})),
            project_id,
        )
        return connection_id

    except asyncpg.UniqueViolationError:
        raise ValueError(
            f"Connection name '{connection_data['connection_name']}' already exists in this project"
        )


async def update_connection(connection_id: int, connection_data: Dict) -> bool:
    """Update existing connection"""
    # Encrypt password if provided
    if "password" in connection_data:
        connection_data["password_encrypted"] = encrypt_password(
            connection_data["password"]
        )
        del connection_data["password"]

    # Build update query
    fields = []
    values = []
    param_num = 1
    for key, value in connection_data.items():
        if key in [
            "host",
            "port",
            "database_name",
            "username",
            "password_encrypted",
            "ssl_enabled",
            "connection_params",
            "is_active",
        ]:
            fields.append(f"{key} = ${param_num}")
            if key == "connection_params" and isinstance(value, dict):
                values.append(json.dumps(value))
            else:
                values.append(value)
            param_num += 1

    if not fields:
        return False

    fields.append("updated_at = NOW()")
    values.append(connection_id)

    query = f"UPDATE {CONNECTIONS_TABLE} SET {', '.join(fields)} WHERE id = ${param_num}"
    result = await execute(query, *values)
    return "UPDATE" in result


async def delete_connection(connection_id: int) -> bool:
    """Delete connection and associated tables"""
    async with get_transaction() as conn:
        # Delete from external_tables first (foreign key)
        await conn.execute(
            f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE connection_id = $1",
            connection_id
        )

        # Delete connection
        result = await conn.execute(
            f"DELETE FROM {CONNECTIONS_TABLE} WHERE id = $1", connection_id
        )

        return "DELETE" in result


async def get_all_connections(project_id: int = None) -> List[Dict]:
    """Get all saved connections (without passwords)"""
    if project_id is not None:
        rows = await fetch(
            f"""
            SELECT id, connection_name, db_type, host, port, database_name, 
                   username, ssl_enabled, is_active, project_id, created_at, updated_at
            FROM {CONNECTIONS_TABLE}
            WHERE project_id = $1
            ORDER BY connection_name
            """,
            project_id
        )
    else:
        rows = await fetch(f"""
            SELECT id, connection_name, db_type, host, port, database_name, 
                   username, ssl_enabled, is_active, project_id, created_at, updated_at
            FROM {CONNECTIONS_TABLE}
            ORDER BY connection_name
        """)

    return [dict(row) for row in rows]


async def get_connection_by_id(connection_id: int) -> Optional[Dict]:
    """Get connection details including decrypted password"""
    row = await fetchrow(f"SELECT * FROM {CONNECTIONS_TABLE} WHERE id = $1", connection_id)

    if not row:
        return None

    connection = dict(row)
    # Decrypt password
    try:
        connection["password"] = decrypt_password(connection["password_encrypted"])
    except Exception as e:
        print(f"Failed to decrypt password: {e}")
        connection["password"] = ""

    del connection["password_encrypted"]

    # Parse connection params
    if connection.get("connection_params"):
        try:
            connection["connection_params"] = json.loads(
                connection["connection_params"]
            )
        except:
            connection["connection_params"] = {}

    return connection


# Alias for backwards compatibility
get_connection_details = get_connection_by_id


def get_connector(connection_id: int) -> DatabaseConnector:
    """Get appropriate connector instance for a connection (sync helper for external DB connections).
    
    Uses synchronous psycopg to avoid conflicts with async event loop.
    This is intentionally synchronous for compatibility with external database connectors.
    """
    import os
    import psycopg
    
    # Build connection string for sync psycopg
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE", "nl_to_sql")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "")
    sslmode = os.getenv("PGSSLMODE", "prefer")
    
    conninfo = f"host={host} port={port} dbname={database} user={user} password={password} sslmode={sslmode}"
    
    # Use sync psycopg connection
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {CONNECTIONS_TABLE} WHERE id = %s",
                (connection_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            connection = dict(zip(columns, row))
    
    # Decrypt password
    if connection.get("password_encrypted"):
        try:
            connection["password"] = decrypt_password(connection["password_encrypted"])
        except Exception as e:
            print(f"Failed to decrypt password: {e}")
            connection["password"] = ""
    else:
        connection["password"] = ""
    
    # Parse connection params
    if connection.get("connection_params"):
        try:
            connection["connection_params"] = json.loads(connection["connection_params"])
        except:
            connection["connection_params"] = {}
    else:
        connection["connection_params"] = {}

    config = ConnectionConfig(
        host=connection["host"],
        port=connection["port"],
        database=connection["database_name"],
        username=connection["username"],
        password=connection["password"],
        ssl_enabled=bool(connection["ssl_enabled"]),
        connection_params=connection.get("connection_params", {}),
    )

    db_type = connection["db_type"].lower()
    connector_class = get_connector_class(db_type)

    return connector_class(config)


async def get_connector_async(connection_id: int) -> DatabaseConnector:
    """Get appropriate connector instance for a connection (async version)"""
    connection = await get_connection_by_id(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    config = ConnectionConfig(
        host=connection["host"],
        port=connection["port"],
        database=connection["database_name"],
        username=connection["username"],
        password=connection["password"],
        ssl_enabled=bool(connection["ssl_enabled"]),
        connection_params=connection.get("connection_params", {}),
    )

    db_type = connection["db_type"].lower()
    connector_class = get_connector_class(db_type)

    return connector_class(config)


async def test_connection(connection_id: int) -> Dict:
    """Test if connection is valid"""
    try:
        connector = await get_connector_async(connection_id)
        result = connector.test_connection()
        connector.disconnect()
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


def test_connection_data(connection_data: Dict) -> Dict:
    """Test connection without saving it"""
    try:
        config = ConnectionConfig(
            host=connection_data["host"],
            port=connection_data["port"],
            database=connection_data["database_name"],
            username=connection_data["username"],
            password=connection_data["password"],
            ssl_enabled=connection_data.get("ssl_enabled", False),
            connection_params=connection_data.get("connection_params", {}),
        )

        db_type = connection_data["db_type"].lower()
        connector_class = get_connector_class(db_type)
        connector = connector_class(config)

        result = connector.test_connection()
        connector.disconnect()
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}
