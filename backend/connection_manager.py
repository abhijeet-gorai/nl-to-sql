"""
Connection Manager Module
Manages database connections and credentials with encryption
"""

import sqlite3
import json
from typing import Dict, List, Optional
from cryptography.fernet import Fernet
import os
from db_connector import (
    DatabaseConnector, 
    ConnectionConfig,
    get_connector_class
)

# Get encryption key from environment
ENCRYPTION_KEY = os.getenv('DB_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    # Generate a key for development (in production, this should be set)
    ENCRYPTION_KEY = Fernet.generate_key()
    print("WARNING: Using generated encryption key. Set DB_ENCRYPTION_KEY in production.")
    print(f"Generated key: {ENCRYPTION_KEY.decode()}")

cipher_suite = Fernet(ENCRYPTION_KEY if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY.encode())

DB_PATH = "database.db"
CONNECTIONS_TABLE = "db_connections"
EXTERNAL_TABLES_TABLE = "external_tables"


def init_connections_table():
    """Initialize the connections and external tables tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create connections table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {CONNECTIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_name TEXT UNIQUE NOT NULL,
            db_type TEXT NOT NULL,
            host TEXT,
            port INTEGER,
            database_name TEXT,
            username TEXT,
            password_encrypted TEXT,
            ssl_enabled BOOLEAN DEFAULT 0,
            connection_params TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create external tables table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {EXTERNAL_TABLES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id INTEGER NOT NULL,
            schema_name TEXT,
            table_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            columns_metadata TEXT,
            row_count INTEGER,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_selected BOOLEAN DEFAULT 0,
            FOREIGN KEY (connection_id) REFERENCES {CONNECTIONS_TABLE}(id) ON DELETE CASCADE,
            UNIQUE(connection_id, schema_name, table_name)
        )
    """)
    
    # Update app_metadata table to support external sources
    try:
        cursor.execute("ALTER TABLE app_metadata ADD COLUMN source_type TEXT DEFAULT 'csv'")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    try:
        cursor.execute("ALTER TABLE app_metadata ADD COLUMN connection_id INTEGER")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    try:
        cursor.execute("ALTER TABLE app_metadata ADD COLUMN schema_name TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    conn.commit()
    conn.close()


def encrypt_password(password: str) -> str:
    """Encrypt password using Fernet symmetric encryption"""
    return cipher_suite.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt password"""
    return cipher_suite.decrypt(encrypted.encode()).decode()


def create_connection(connection_data: Dict) -> int:
    """Create new database connection"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Encrypt password
        encrypted_pwd = encrypt_password(connection_data['password'])
        
        cursor.execute(f"""
            INSERT INTO {CONNECTIONS_TABLE} 
            (connection_name, db_type, host, port, database_name, username, 
             password_encrypted, ssl_enabled, connection_params)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            connection_data['connection_name'],
            connection_data['db_type'],
            connection_data.get('host'),
            connection_data.get('port'),
            connection_data.get('database_name'),
            connection_data.get('username'),
            encrypted_pwd,
            connection_data.get('ssl_enabled', False),
            json.dumps(connection_data.get('connection_params', {}))
        ))
        
        conn.commit()
        connection_id = cursor.lastrowid
        return connection_id
        
    except sqlite3.IntegrityError:
        raise ValueError(f"Connection name '{connection_data['connection_name']}' already exists")
    finally:
        conn.close()


def update_connection(connection_id: int, connection_data: Dict) -> bool:
    """Update existing connection"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Encrypt password if provided
        if 'password' in connection_data:
            connection_data['password_encrypted'] = encrypt_password(connection_data['password'])
            del connection_data['password']
        
        # Build update query
        fields = []
        values = []
        for key, value in connection_data.items():
            if key in ['host', 'port', 'database_name', 'username', 'password_encrypted', 
                      'ssl_enabled', 'connection_params', 'is_active']:
                fields.append(f"{key} = ?")
                if key == 'connection_params' and isinstance(value, dict):
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if not fields:
            return False
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(connection_id)
        
        query = f"UPDATE {CONNECTIONS_TABLE} SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        return cursor.rowcount > 0
        
    finally:
        conn.close()


def delete_connection(connection_id: int) -> bool:
    """Delete connection and associated tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Delete from external_tables first (foreign key)
        cursor.execute(f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE connection_id = ?", (connection_id,))
        
        # Delete connection
        cursor.execute(f"DELETE FROM {CONNECTIONS_TABLE} WHERE id = ?", (connection_id,))
        
        conn.commit()
        return cursor.rowcount > 0
        
    finally:
        conn.close()


def get_all_connections() -> List[Dict]:
    """Get all saved connections (without passwords)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT id, connection_name, db_type, host, port, database_name, 
               username, ssl_enabled, is_active, created_at, updated_at
        FROM {CONNECTIONS_TABLE}
        ORDER BY connection_name
    """)
    
    connections = []
    for row in cursor.fetchall():
        connections.append(dict(row))
    
    conn.close()
    return connections


def get_connection(connection_id: int) -> Optional[Dict]:
    """Get connection details including decrypted password"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM {CONNECTIONS_TABLE} WHERE id = ?", (connection_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    connection = dict(row)
    # Decrypt password
    try:
        connection['password'] = decrypt_password(connection['password_encrypted'])
    except Exception as e:
        print(f"Failed to decrypt password: {e}")
        connection['password'] = ""
    
    del connection['password_encrypted']
    
    # Parse connection params
    if connection.get('connection_params'):
        try:
            connection['connection_params'] = json.loads(connection['connection_params'])
        except:
            connection['connection_params'] = {}
    
    return connection


def get_connector(connection_id: int) -> DatabaseConnector:
    """Get appropriate connector instance for a connection"""
    connection = get_connection(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")
    
    config = ConnectionConfig(
        host=connection['host'],
        port=connection['port'],
        database=connection['database_name'],
        username=connection['username'],
        password=connection['password'],
        ssl_enabled=bool(connection['ssl_enabled']),
        connection_params=connection.get('connection_params', {})
    )
    
    db_type = connection['db_type'].lower()
    connector_class = get_connector_class(db_type)
    
    return connector_class(config)


def test_connection(connection_id: int) -> Dict:
    """Test if connection is valid"""
    try:
        connector = get_connector(connection_id)
        result = connector.test_connection()
        connector.disconnect()
        return result
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


def test_connection_data(connection_data: Dict) -> Dict:
    """Test connection without saving it"""
    try:
        config = ConnectionConfig(
            host=connection_data['host'],
            port=connection_data['port'],
            database=connection_data['database_name'],
            username=connection_data['username'],
            password=connection_data['password'],
            ssl_enabled=connection_data.get('ssl_enabled', False),
            connection_params=connection_data.get('connection_params', {})
        )
        
        db_type = connection_data['db_type'].lower()
        connector_class = get_connector_class(db_type)
        connector = connector_class(config)
        
        result = connector.test_connection()
        connector.disconnect()
        return result
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
