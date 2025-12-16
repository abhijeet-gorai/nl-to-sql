import sqlite3
import pandas as pd
import os
import json
import random
import string
from typing import List, Dict, Optional

DB_PATH = "database.db"
METADATA_TABLE = "app_metadata"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create metadata table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT UNIQUE NOT NULL,
            original_filename TEXT NOT NULL,
            description TEXT,
            columns_metadata TEXT  -- JSON string
        )
    """)
    conn.commit()
    conn.close()

def check_table_exists(table_name: str) -> bool:
    """Checks if a table name already exists in the metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT 1 FROM {METADATA_TABLE} WHERE table_name = ?", (table_name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def generate_random_suffix(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_table_name(filename: str) -> str:
    # Sanitize: Remove extension, non-alphanumeric, lowercase
    base = os.path.splitext(filename)[0].lower()
    clean_base = "".join(c for c in base if c.isalnum() or c == '_')
    if not clean_base:
        clean_base = "table"
    
    # Default behavior: Add random suffix to ensure uniqueness for fallback
    return f"{clean_base}_{generate_random_suffix()}"

def analyze_csv(file_path: str, original_filename: str) -> Dict:
    """
    Reads CSV, infers schema, returns preview and suggested metadata.
    Does NOT create the table yet.
    """
    try:
        # Read a subset to infer types and preview
        df_preview = pd.read_csv(file_path, nrows=5)
        # Read 0 rows to get columns cheaply
        df_headers = pd.read_csv(file_path, nrows=0)
        
        columns = []
        for col in df_headers.columns:
            # Simple heuristic for type
            dtype = "TEXT" # Default
            if col in df_preview.columns:
                 pd_type = str(df_preview[col].dtype)
                 if 'int' in pd_type: dtype = "INTEGER"
                 elif 'float' in pd_type: dtype = "REAL"
            
            columns.append({
                "name": col,
                "type": dtype,
                "description": f"Column '{col}'" 
            })

        preview = df_preview.fillna("").to_dict(orient="records")
        
        # Quick row count
        row_count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            row_count = sum(1 for _ in f) - 1
            
        suggested_name = generate_table_name(original_filename)
        
        return {
            "file_path": file_path, # Temp used for next step
            "original_filename": original_filename,
            "suggested_table_name": suggested_name,
            "description": f"Dataset imported from {original_filename}",
            "columns": columns,
            "preview": preview,
            "row_count": row_count
        }
    except Exception as e:
        raise Exception(f"Failed to analyze CSV: {str(e)}")

def register_table(file_path: str, metadata: Dict):
    """
    Creates the table in SQLite and saves metadata.
    metadata structure: { table_name, description, columns: [{name, description, type}] }
    """
    table_name = metadata['table_name']
    
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_csv(file_path)
        
        # Sanitize columns in DF to match metadata names if we allow renaming later
        # For now, just ensuring valid SQL identifiers 
        df.columns = [c.strip().replace(" ", "_") for c in df.columns]
        
        # Write data
        df.to_sql(table_name, conn, if_exists='fail', index=False)
        
        # Save Metadata
        cursor = conn.cursor()
        columns_json = json.dumps(metadata.get('columns', []))
        cursor.execute(f"""
            INSERT INTO {METADATA_TABLE} (table_name, original_filename, description, columns_metadata)
            VALUES (?, ?, ?, ?)
        """, (table_name, metadata.get('original_filename', 'unknown'), metadata.get('description', ''), columns_json))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        raise Exception(f"Table '{table_name}' already exists.")
    except Exception as e:
        raise Exception(f"Failed to register table: {str(e)}")

def delete_table(table_name: str) -> bool:
    """
    Drops the table and removes its metadata.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Drop table
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # Remove metadata
        cursor.execute(f"DELETE FROM {METADATA_TABLE} WHERE table_name = ?", (table_name,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to delete table {table_name}: {e}")
        return False
    finally:
        conn.close()

def get_all_tables() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if metadata table exists (migration check)
    try:
        cursor.execute(f"SELECT * FROM {METADATA_TABLE}")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # If table doesn't exist, maybe it's old DB. Init and try again.
        init_db()
        return []
    
    tables = []
    for row in rows:
        tables.append({
            "id": row["id"],
            "table_name": row["table_name"],
            "original_filename": row["original_filename"],
            "description": row["description"],
            "columns": json.loads(row["columns_metadata"]) if row["columns_metadata"] else []
        })
    conn.close()
    return tables

def get_table_context(table_names: List[str]) -> str:
    """
    Returns a formatted string describing the selected tables and their metadata for the LLM.
    """
    if not table_names:
        return ""
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    placeholders = ','.join('?' for _ in table_names)
    try:
        cursor.execute(f"SELECT * FROM {METADATA_TABLE} WHERE table_name IN ({placeholders})", table_names)
        rows = cursor.fetchall()
    except:
        return ""
    conn.close()
    
    context = ""
    for row in rows:
        context += f"Table: {row['table_name']}\n"
        context += f"Description: {row['description']}\n"
        context += "Columns:\n"
        cols = json.loads(row["columns_metadata"]) if row["columns_metadata"] else []
        for col in cols:
            context += f"  - {col['name']} ({col['type']}): {col.get('description', '')}\n"
        context += "\n"
        
    return context

def execute_query(query: str):
    """
    Executes a read-only SQL query.
    """
    if not query.strip().lower().startswith("select"):
        return "Error: Only SELECT queries are allowed."
        
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df.to_markdown(index=False)
    except Exception as e:
        conn.close()
        return f"Error executing query: {str(e)}"
