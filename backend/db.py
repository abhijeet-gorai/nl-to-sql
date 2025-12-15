import pandas as pd
from sqlalchemy import create_engine, inspect, text
import os

DB_PATH = "sqlite:///./test.db"
engine = create_engine(DB_PATH)

def init_db():
    # SQLite is file-based, so just ensuring the engine works is enough usually.
    # We can create a dummy connection.
    try:
        with engine.connect() as conn:
            pass
    except Exception as e:
        print(f"DB Init Error: {e}")

def process_csv(file_path: str, table_name: str = "uploaded_data"):
    """
    Reads a CSV file and creates a table in SQLite.
    Dynamically infers types via pandas.
    """
    try:
        df = pd.read_csv(file_path)
        # Sanitize column names (remove spaces, special chars if needed) - keeping simple for now
        df.columns = [c.strip().replace(" ", "_").lower() for c in df.columns]
        
        # Write to SQL (replace if exists for this demo)
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        return {"columns": list(df.columns), "row_count": len(df)}
    except Exception as e:
        raise Exception(f"Error processing CSV: {e}")

def get_db_schema():
    """
    Returns the schema of the database for the LLM.
    """
    inspector = inspect(engine)
    schema_info = ""
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        schema_info += f"Table: {table_name}\nColumns:\n"
        for col in columns:
            schema_info += f"  - {col['name']} ({col['type']})\n"
    return schema_info

def execute_sql(query: str):
    """
    Executes a read-only SQL query.
    """
    # Basic safety check to prevent modification
    if not query.strip().lower().startswith("select"):
        return "Error: Only SELECT queries are allowed."

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            keys = result.keys()
            rows = result.fetchall()
            return [dict(zip(keys, row)) for row in rows]
    except Exception as e:
        return f"Error executing SQL: {e}"
