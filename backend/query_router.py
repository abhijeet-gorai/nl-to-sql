"""
Query Router Module
Routes queries to appropriate database based on table source
"""

import sqlite3
import pandas as pd
from typing import List, Dict, Optional
import sqlglot
from sqlglot import exp

import connection_manager as cm
import db

DB_PATH = "database.db"


def parse_query_tables(query: str) -> List[Dict[str, Optional[str]]]:
    """
    Extract table names from SQL query using sqlglot.
    Returns list of dicts: {'schema': str|None, 'table': str}
    Excludes CTEs defined within the query.
    """
    try:
        parsed = sqlglot.parse_one(query)
    except Exception as e:
        # If parsing fails, fall back to empty list or raise error?
        # For security, we should probably treat unparsable queries as suspicious or handled by regex fallback,
        # but here we'll assume valid SQL generation from the agent.
        print(f"Warning: Failed to parse query with sqlglot: {e}")
        return []

    tables = []
    cte_names = set()

    # Find CTE definitions to exclude them
    for cte in parsed.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.upper())

    # Find all table references
    for table in parsed.find_all(exp.Table):
        # sqlglot treats function calls sometimes as tables if ambiguous, but usually correct.
        # Check if it's a CTE reference
        table_name = table.name.upper()
        if table_name in cte_names:
            continue

        schema = table.db
        if schema:
            schema = schema.lower()  # Normalize
        else:
            schema = None

        tables.append(
            {
                "schema": schema,
                "table": table.name.lower(),  # Normalize
            }
        )

    # Deduplicate based on schema+table
    unique_tables = []
    seen = set()
    for t in tables:
        key = (t["schema"], t["table"])
        if key not in seen:
            seen.add(key)
            unique_tables.append(t)

    return unique_tables


def get_table_source(table_name: str) -> Optional[Dict]:
    """Get source information for a table"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if it's a CSV table (in app_metadata)
    cursor.execute(
        """
        SELECT table_name, 'csv' as source_type, NULL as connection_id, NULL as schema_name
        FROM app_metadata
        WHERE table_name = ? AND (source_type = 'csv' OR source_type IS NULL)
    """,
        (table_name,),
    )

    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    # Check if it's an external table
    cursor.execute(
        """
        SELECT 
            et.table_name,
            'external' as source_type,
            et.connection_id,
            et.schema_name,
            c.db_type
        FROM external_tables et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.display_name = ? OR et.table_name = ?
    """,
        (table_name, table_name),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)

    return None


def get_table_sources(selected_tables: List[Dict]) -> Dict[str, Dict]:
    """
    Format table selection objects into source dictionary.
    Now accepts list of dictionaries (from TableSelection model).
    """
    sources = {}
    for table in selected_tables:
        # handle input as dict or object
        if hasattr(table, "dict"):
            t_dict = table.dict()
        else:
            t_dict = dict(table)

        table_name = t_dict["table_name"]
        sources[table_name] = {
            "table_name": table_name,
            "source_type": t_dict["source_type"],
            "connection_id": t_dict.get("connection_id"),
            "schema_name": t_dict.get("schema"),
        }

    return sources


def validate_query_sources(table_sources: Dict[str, Dict]) -> Dict:
    """Validate that all tables exist and check for cross-database queries"""
    # Note: With explicit selection, we assume existence based on ID,
    # but we should still enforce single-source constraints.

    # Check if query spans multiple external databases
    connection_ids = set()
    has_csv = False

    for _, source in table_sources.items():
        if source["source_type"] == "csv":
            has_csv = True
        else:
            if source.get("connection_id"):
                connection_ids.add(source["connection_id"])

    # For now, we don't support cross-database joins
    if len(connection_ids) > 1:
        return {
            "valid": False,
            "error": "Cross-database queries are not supported. Please query tables from a single database.",
        }

    if has_csv and len(connection_ids) > 0:
        return {
            "valid": False,
            "error": "Cannot mix CSV tables with external database tables in the same query.",
        }

    return {"valid": True}


def execute_federated_query(query: str, selected_tables: List[Dict]) -> pd.DataFrame:
    """Execute query against appropriate database based on selected tables"""
    if not selected_tables:
        raise ValueError("No tables selected")

    # 1. Parse tables from the query
    parsed_tables = parse_query_tables(query)

    # 2. Validate extracted tables against selected tables
    # Build a lookup for selected tables: (schema, table_name) -> Source Info
    # For CSVs, schema is None.
    selected_lookup = set()
    for st in selected_tables:
        # Handle dict or object
        if hasattr(st, "dict"):
            st = st.dict()
        else:
            st = dict(st)

        t_name = st["table_name"].lower()
        s_name = st.get("schema")
        if s_name:
            s_name = s_name.lower()

        # We store pairs of (schema, table)
        # Note: If schema is None, it matches parsed tables with None schema OR un-schema'd references (if allowed)
        selected_lookup.add((s_name, t_name))

    for pt in parsed_tables:
        pt_table = pt["table"]
        pt_schema = pt["schema"]

        # Check for strict match
        # Case 1: Query has schema (e.g. public.orders). Must match exactly.
        if pt_schema:
            if (pt_schema, pt_table) not in selected_lookup:
                raise ValueError(
                    f"Security Error: Access to table '{pt_schema}.{pt_table}' is denied. It is not in the selected tables list."
                )

        # Case 2: Query has NO schema (e.g. orders).
        # We allow it IF there's a selected table with that name (ignoring schema for convenience if no ambiguity?)
        # OR we strictly require that if the selected table has a schema, the query MUST use it?
        # User requested: "make sure that the query doesn't have any other table apart from the selected_tables"
        # Safest approach: If query has no schema, we check if ANY selected table matches that name.
        # BUT if multiple selected tables have same name (diff schemas), referencing without schema is ambiguous.
        # However, we are just validating 'is this table allowed'.
        else:
            # Check if (None, table) exists (local CSV) OR if (_, table) exists (External)
            # If the user selected 'public.orders', and query asks for 'orders', is that allowed?
            # Typically SQL requires schema if not in search path.
            # Here we just want to block 'users' if 'users' wasn't selected.

            found = False
            for sel_schema, sel_table in selected_lookup:
                if sel_table == pt_table:
                    found = True
                    break

            if not found:
                raise ValueError(
                    f"Security Error: Access to table '{pt_table}' is denied. It is not in the selected tables list."
                )

    # Get sources for selected tables (tables are already in source format mostly)
    table_sources = get_table_sources(selected_tables)

    # Validate that all selected tables exist and are from same source
    validation = validate_query_sources(table_sources)
    if not validation["valid"]:
        raise ValueError(validation["error"])

    # Determine which database to query based on first selected table
    # We can pick any because we validated they are unique source
    first_table = list(table_sources.values())[0]

    if first_table["source_type"] == "csv":
        # Query local SQLite database
        return db.get_raw_dataframe(query)
    else:
        # Query external database
        connection_id = first_table["connection_id"]
        connector = cm.get_connector(connection_id)

        try:
            result = connector.execute_query(query)
            connector.disconnect()
            return result
        except Exception as e:
            connector.disconnect()
            raise Exception(f"Query execution failed: {str(e)}")


def build_table_context_federated(table_names: List[str]) -> str:
    """Build context string including source information for federated queries"""
    if not table_names:
        return ""

    table_sources = get_table_sources(table_names)

    context = ""

    # Group tables by source
    csv_tables = []
    external_tables_by_conn = {}

    for table_name, source in table_sources.items():
        if source is None:
            continue

        if source["source_type"] == "csv":
            csv_tables.append(table_name)
        else:
            conn_id = source["connection_id"]
            if conn_id not in external_tables_by_conn:
                external_tables_by_conn[conn_id] = []
            external_tables_by_conn[conn_id].append(table_name)

    # Add CSV tables context
    if csv_tables:
        context += "=== LOCAL CSV TABLES ===\n"
        context += db.get_table_context(csv_tables)
        context += "\n"

    # Add external tables context
    for conn_id, tables in external_tables_by_conn.items():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get connection info
        cursor.execute(
            "SELECT connection_name, db_type FROM db_connections WHERE id = ?",
            (conn_id,),
        )
        conn_info = cursor.fetchone()

        if conn_info:
            context += f"=== EXTERNAL DATABASE: {conn_info['connection_name']} ({conn_info['db_type']}) ===\n"

        # Get table metadata
        for table_name in tables:
            cursor.execute(
                """
                SELECT display_name, schema_name, table_name, description, columns_metadata
                FROM external_tables
                WHERE connection_id = ? AND (display_name = ? OR table_name = ?)
            """,
                (conn_id, table_name, table_name),
            )

            row = cursor.fetchone()
            if row:
                context += f"Table: {row['display_name']}\n"
                context += f"Schema: {row['schema_name']}\n"
                context += f"Description: {row['description']}\n"
                context += "Columns:\n"

                try:
                    import json

                    columns = (
                        json.loads(row["columns_metadata"])
                        if row["columns_metadata"]
                        else []
                    )
                    for col in columns:
                        context += f"  - {col['name']} ({col['type']}): {col.get('description', '')}\n"
                except:
                    pass

                context += "\n"

        conn.close()

    return context


def get_all_available_tables(project_id: int = None) -> List[Dict]:
    """Get all available tables (CSV + External) for selection, optionally filtered by project"""
    tables = []

    # Get CSV tables
    csv_tables = db.get_all_tables(project_id)
    for table in csv_tables:
        table["source_type"] = "csv"
        table["source_name"] = "Local CSV"
        tables.append(table)

    # Get external tables
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT 
            et.id,
            et.display_name as table_name,
            et.description,
            et.columns_metadata,
            et.schema_name,
            'external' as source_type,
            c.connection_name as source_name,
            c.db_type,
            et.connection_id,
            et.project_id
        FROM external_tables et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.is_selected = 1
    """
    params = []

    if project_id is not None:
        query += " AND et.project_id = ?"
        params.append(project_id)

    query += " ORDER BY et.display_name"

    cursor.execute(query, tuple(params))

    for row in cursor.fetchall():
        table = dict(row)
        # Parse columns
        if table.get("columns_metadata"):
            try:
                import json

                table["columns"] = json.loads(table["columns_metadata"])
            except:
                table["columns"] = []
        del table["columns_metadata"]
        tables.append(table)

    conn.close()

    return tables
