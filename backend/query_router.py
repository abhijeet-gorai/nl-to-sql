"""
Query Router Module
Routes queries to appropriate database based on table source
"""

import sqlite3
import pandas as pd
from typing import List, Dict, Optional
import re
import connection_manager as cm
import db

DB_PATH = "database.db"


def parse_query_tables(query: str) -> List[str]:
    """Extract table names from SQL query"""
    # Simple regex to find table names after FROM and JOIN
    # This is a basic implementation - could be enhanced with proper SQL parsing
    query_upper = query.upper()
    
    # Remove subqueries and strings to avoid false matches
    cleaned_query = re.sub(r'\([^)]*\)', '', query_upper)
    cleaned_query = re.sub(r"'[^']*'", '', cleaned_query)
    cleaned_query = re.sub(r'"[^"]*"', '', cleaned_query)
    
    tables = []
    
    # Find tables after FROM
    from_pattern = r'FROM\s+([a-zA-Z0-9_]+)'
    from_matches = re.findall(from_pattern, cleaned_query)
    tables.extend(from_matches)
    
    # Find tables after JOIN
    join_pattern = r'JOIN\s+([a-zA-Z0-9_]+)'
    join_matches = re.findall(join_pattern, cleaned_query)
    tables.extend(join_matches)
    
    # Remove duplicates and convert to lowercase
    tables = list(set([t.lower() for t in tables]))
    
    return tables


def get_table_source(table_name: str) -> Optional[Dict]:
    """Get source information for a table"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if it's a CSV table (in app_metadata)
    cursor.execute("""
        SELECT table_name, 'csv' as source_type, NULL as connection_id, NULL as schema_name
        FROM app_metadata
        WHERE table_name = ? AND (source_type = 'csv' OR source_type IS NULL)
    """, (table_name,))
    
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
    
    # Check if it's an external table
    cursor.execute("""
        SELECT 
            et.table_name,
            'external' as source_type,
            et.connection_id,
            et.schema_name,
            c.db_type
        FROM external_tables et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.display_name = ? OR et.table_name = ?
    """, (table_name, table_name))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    
    return None


def get_table_sources(table_names: List[str]) -> Dict[str, Dict]:
    """Map table names to their source connections"""
    sources = {}
    for table_name in table_names:
        source = get_table_source(table_name)
        if source:
            sources[table_name] = source
        else:
            # Table not found
            sources[table_name] = None
    
    return sources


def validate_query_sources(table_sources: Dict[str, Dict]) -> Dict:
    """Validate that all tables exist and check for cross-database queries"""
    # Check for missing tables
    missing_tables = [name for name, source in table_sources.items() if source is None]
    if missing_tables:
        return {
            "valid": False,
            "error": f"Tables not found: {', '.join(missing_tables)}"
        }
    
    # Check if query spans multiple external databases
    connection_ids = set()
    has_csv = False
    
    for table_name, source in table_sources.items():
        if source['source_type'] == 'csv':
            has_csv = True
        else:
            connection_ids.add(source['connection_id'])
    
    # For now, we don't support cross-database joins
    if len(connection_ids) > 1:
        return {
            "valid": False,
            "error": "Cross-database queries are not supported. Please query tables from a single database."
        }
    
    if has_csv and len(connection_ids) > 0:
        return {
            "valid": False,
            "error": "Cannot mix CSV tables with external database tables in the same query."
        }
    
    return {"valid": True}


def execute_federated_query(query: str, selected_table_names: List[str]) -> pd.DataFrame:
    """Execute query against appropriate database based on selected tables"""
    if not selected_table_names:
        raise ValueError("No tables selected")
    
    # Get sources for selected tables (not from parsing query)
    table_sources = get_table_sources(selected_table_names)
    
    # Validate that all selected tables exist and are from same source
    validation = validate_query_sources(table_sources)
    if not validation['valid']:
        raise ValueError(validation['error'])
    
    # Determine which database to query based on first selected table
    first_table = list(table_sources.values())[0]
    
    if first_table['source_type'] == 'csv':
        # Query local SQLite database
        return db.get_raw_dataframe(query)
    else:
        # Query external database
        connection_id = first_table['connection_id']
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
        
        if source['source_type'] == 'csv':
            csv_tables.append(table_name)
        else:
            conn_id = source['connection_id']
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
        cursor.execute("SELECT connection_name, db_type FROM db_connections WHERE id = ?", (conn_id,))
        conn_info = cursor.fetchone()
        
        if conn_info:
            context += f"=== EXTERNAL DATABASE: {conn_info['connection_name']} ({conn_info['db_type']}) ===\n"
        
        # Get table metadata
        for table_name in tables:
            cursor.execute("""
                SELECT display_name, schema_name, table_name, description, columns_metadata
                FROM external_tables
                WHERE connection_id = ? AND (display_name = ? OR table_name = ?)
            """, (conn_id, table_name, table_name))
            
            row = cursor.fetchone()
            if row:
                context += f"Table: {row['display_name']}\n"
                context += f"Schema: {row['schema_name']}\n"
                context += f"Description: {row['description']}\n"
                context += "Columns:\n"
                
                try:
                    import json
                    columns = json.loads(row['columns_metadata']) if row['columns_metadata'] else []
                    for col in columns:
                        context += f"  - {col['name']} ({col['type']}): {col.get('description', '')}\n"
                except:
                    pass
                
                context += "\n"
        
        conn.close()
    
    return context


def get_all_available_tables() -> List[Dict]:
    """Get all available tables (CSV + External) for selection"""
    tables = []
    
    # Get CSV tables
    csv_tables = db.get_all_tables()
    for table in csv_tables:
        table['source_type'] = 'csv'
        table['source_name'] = 'Local CSV'
        tables.append(table)
    
    # Get external tables
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            et.id,
            et.display_name as table_name,
            et.description,
            et.columns_metadata,
            et.schema_name,
            'external' as source_type,
            c.connection_name as source_name,
            c.db_type,
            et.connection_id
        FROM external_tables et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.is_selected = 1
        ORDER BY et.display_name
    """)
    
    for row in cursor.fetchall():
        table = dict(row)
        # Parse columns
        if table.get('columns_metadata'):
            try:
                import json
                table['columns'] = json.loads(table['columns_metadata'])
            except:
                table['columns'] = []
        del table['columns_metadata']
        tables.append(table)
    
    conn.close()
    
    return tables
