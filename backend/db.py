import pandas as pd
import os
import json
import random
import string
from typing import List, Dict, Optional
import asyncpg

from database_config import get_connection, execute, fetch, fetchrow, fetchval, get_connection_string
from sql_utils import is_read_only_sql

METADATA_TABLE = "app_metadata"


async def init_db():
    async with get_connection() as conn:
        # Create metadata table
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
                id SERIAL PRIMARY KEY,
                table_name TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                description TEXT,
                columns_metadata TEXT,
                project_id INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(table_name, project_id)
            )
        """)


async def check_table_exists(table_name: str, project_id: int = None) -> bool:
    """Checks if a table name already exists in the metadata for a project."""
    if project_id is not None:
        result = await fetchrow(
            f"SELECT 1 FROM {METADATA_TABLE} WHERE table_name = $1 AND project_id = $2",
            table_name, project_id
        )
    else:
        result = await fetchrow(
            f"SELECT 1 FROM {METADATA_TABLE} WHERE table_name = $1", table_name
        )
    return result is not None


def generate_random_suffix(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_table_name(filename: str) -> str:
    # Sanitize: Remove extension, non-alphanumeric, lowercase
    base = os.path.splitext(filename)[0].lower()
    clean_base = "".join(c for c in base if c.isalnum() or c == "_")
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
        df_preview.columns = [c.strip().replace(" ", "_").lower() for c in df_preview.columns]
        # Read 0 rows to get columns cheaply
        df_headers = pd.read_csv(file_path, nrows=0)
        df_headers.columns = [c.strip().replace(" ", "_").lower() for c in df_headers.columns]

        columns = []
        for col in df_headers.columns:
            # Simple heuristic for type
            dtype = "TEXT"  # Default
            if col in df_preview.columns:
                pd_type = str(df_preview[col].dtype)
                if "int" in pd_type:
                    dtype = "INTEGER"
                elif "float" in pd_type:
                    dtype = "REAL"

            columns.append(
                {"name": col, "type": dtype, "description": f"Column '{col}'"}
            )

        preview = df_preview.fillna("").to_dict(orient="records")

        # Quick row count
        row_count = 0
        with open(file_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for _ in f) - 1

        suggested_name = generate_table_name(original_filename)

        return {
            "file_path": file_path,  # Temp used for next step
            "original_filename": original_filename,
            "suggested_table_name": suggested_name,
            "description": f"Dataset imported from {original_filename}",
            "columns": columns,
            "preview": preview,
            "row_count": row_count,
        }
    except Exception as e:
        raise Exception(f"Failed to analyze CSV: {str(e)}")


async def register_table(file_path: str, metadata: Dict, project_id: int = None):
    """
    Creates the table in PostgreSQL and saves metadata.
    metadata structure: { table_name, description, columns: [{name, description, type}] }
    """
    table_name = metadata["table_name"]

    try:
        df = pd.read_csv(file_path)

        # Sanitize columns in DF to match metadata names if we allow renaming later
        # For now, just ensuring valid SQL identifiers
        df.columns = [c.strip().replace(" ", "_").lower() for c in df.columns]

        # Use SQLAlchemy for pandas to_sql with PostgreSQL
        from sqlalchemy import create_engine

        engine = create_engine(get_connection_string().replace("postgresql://", "postgresql+psycopg://"))
        
        # Write data
        df.to_sql(table_name, engine, if_exists="fail", index=False)

        # Save Metadata
        columns_json = json.dumps(metadata.get("columns", []))
        await execute(
            f"""
            INSERT INTO {METADATA_TABLE} (table_name, original_filename, description, columns_metadata, project_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            table_name,
            metadata.get("original_filename", "unknown"),
            metadata.get("description", ""),
            columns_json,
            project_id,
        )

        return True
    except asyncpg.UniqueViolationError:
        raise Exception(f"Table '{table_name}' already exists.")
    except Exception as e:
        if "already exists" in str(e).lower():
            raise Exception(f"Table '{table_name}' already exists.")
        raise Exception(f"Failed to register table: {str(e)}")


async def update_table_metadata(
    table_name: str, metadata: Dict, project_id: int = None
) -> bool:
    """
    Updates description and columns_metadata for an existing table.
    """
    try:
        columns_json = json.dumps(metadata.get("columns", []))

        if project_id is not None:
            result = await execute(
                f"""
                UPDATE {METADATA_TABLE}
                SET description = $1, columns_metadata = $2
                WHERE table_name = $3 AND project_id = $4
                """,
                metadata.get("description", ""), columns_json, table_name, project_id
            )
        else:
            result = await execute(
                f"""
                UPDATE {METADATA_TABLE}
                SET description = $1, columns_metadata = $2
                WHERE table_name = $3
                """,
                metadata.get("description", ""), columns_json, table_name
            )

        return "UPDATE" in result
    except Exception as e:
        print(f"Failed to update metadata for {table_name}: {e}")
        raise e


async def delete_table(table_name: str, project_id: int = None) -> bool:
    """
    Drops the table and removes its metadata.
    Returns False if the table does not exist.
    """
    async with get_connection() as conn:
        try:
            # Check if table exists in PostgreSQL
            result = await conn.fetchrow(
                """
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = $1
                """,
                table_name
            )
            table_exists = result is not None

            if not table_exists:
                return False

            # Drop table (use quotes to handle case sensitivity)
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            # Remove metadata
            if project_id is not None:
                await conn.execute(
                    f"DELETE FROM {METADATA_TABLE} WHERE table_name = $1 AND project_id = $2",
                    table_name, project_id
                )
            else:
                await conn.execute(
                    f"DELETE FROM {METADATA_TABLE} WHERE table_name = $1", table_name
                )

            return True

        except Exception as e:
            print(f"Failed to delete table {table_name}: {e}")
            return False


async def get_all_tables(project_id: int = None) -> List[Dict]:
    try:
        if project_id is not None:
            rows = await fetch(
                f"SELECT * FROM {METADATA_TABLE} WHERE project_id = $1", project_id
            )
        else:
            rows = await fetch(f"SELECT * FROM {METADATA_TABLE}")

        tables = []
        for row in rows:
            tables.append(
                {
                    "id": row["id"],
                    "table_name": row["table_name"],
                    "original_filename": row["original_filename"],
                    "description": row["description"],
                    "columns": json.loads(row["columns_metadata"])
                    if row["columns_metadata"]
                    else [],
                    "project_id": row.get("project_id"),
                }
            )
        return tables
    except asyncpg.UndefinedTableError:
        # If table doesn't exist, init and return empty
        await init_db()
        return []


async def get_table_context(table_names: List[str]) -> str:
    """
    Returns a formatted string describing the selected tables and their metadata for the LLM.
    """
    if not table_names:
        return ""

    try:
        # Build parameterized query
        placeholders = ", ".join(f"${i+1}" for i in range(len(table_names)))
        rows = await fetch(
            f"SELECT * FROM {METADATA_TABLE} WHERE table_name IN ({placeholders})",
            *table_names
        )

        context = ""
        for row in rows:
            context += f"Table: {row['table_name']}\n"
            context += f"Description: {row['description']}\n"
            context += "Columns:\n"
            cols = json.loads(row["columns_metadata"]) if row["columns_metadata"] else []
            for col in cols:
                context += (
                    f"  - {col['name']} ({col['type']}): {col.get('description', '')}\n"
                )
            context += "\n"

        return context
    except Exception:
        return ""


def execute_query(query: str):
    """
    Executes a read-only SQL query.
    """
    if not query.strip().lower().startswith("select"):
        return "Error: Only SELECT queries are allowed."

    try:
        from sqlalchemy import create_engine

        engine = create_engine(get_connection_string().replace("postgresql://", "postgresql+psycopg://"))
        df = pd.read_sql_query(query, engine)
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {str(e)}"


def get_raw_dataframe(query: str) -> Optional[pd.DataFrame]:
    """
    Executes a read-only SQL query and returns the pandas DataFrame directly.
    """
    if not is_read_only_sql(query, dialect="postgres"):
        raise ValueError("Only read-only SELECT queries are allowed")

    from sqlalchemy import create_engine

    engine = create_engine(get_connection_string().replace("postgresql://", "postgresql+psycopg://"))
    df = pd.read_sql_query(query, engine)
    return df
