"""
Metadata Extractor Module
Discovers and enriches metadata from external databases
"""

import sqlite3
import json
from typing import List, Dict
import pandas as pd
from datetime import datetime, date
import connection_manager as cm
import agent

DB_PATH = "database.db"
EXTERNAL_TABLES_TABLE = "external_tables"


def discover_tables(connection_id: int, schema: str = None) -> List[Dict]:
    """Discover all tables in a schema"""
    try:
        connector = cm.get_connector(connection_id)
        
        # If no schema specified, get first available schema
        if not schema:
            schemas = connector.get_schemas()
            if not schemas:
                connector.disconnect()
                return []
            schema = schemas[0]
        
        tables = connector.get_tables(schema)
        connector.disconnect()
        
        return tables
    except Exception as e:
        raise Exception(f"Failed to discover tables: {str(e)}")


def extract_table_metadata(connection_id: int, schema: str, table: str) -> Dict:
    """Extract detailed metadata for a specific table"""
    try:
        connector = cm.get_connector(connection_id)
        metadata = connector.get_table_metadata(schema, table)
        connector.disconnect()
        
        return metadata
    except Exception as e:
        raise Exception(f"Failed to extract table metadata: {str(e)}")


def enrich_metadata_with_ai(table_metadata: Dict, sample_data: pd.DataFrame) -> Dict:
    """Use AI to generate descriptions for table and columns"""
    try:
        preview_df = sample_data.head(5).copy()

        def make_json_safe(val):
            if isinstance(val, (pd.Timestamp, date, datetime)):
                return val.isoformat()
            return val

        # Apply element-wise conversion
        preview_df = preview_df.applymap(make_json_safe).fillna("")

        preview_data = {
            "preview": preview_df.to_dict(orient="records"),
            "columns": table_metadata["columns"]
        }
        
        # Use existing AI metadata generation
        table_name = table_metadata['table_name']
        enriched = agent.generate_table_metadata(
            preview_data, 
            table_name,
            []  # No need to check existing names for external tables
        )
        
        # Merge AI descriptions with existing metadata
        if enriched:
            table_metadata['description'] = enriched.get('description', table_metadata.get('description', ''))
            
            # Update column descriptions
            ai_cols = {c['name']: c.get('description', '') for c in enriched.get('columns', [])}
            for col in table_metadata['columns']:
                if col['name'] in ai_cols and ai_cols[col['name']]:
                    col['description'] = ai_cols[col['name']]
        
        return table_metadata
        
    except Exception as e:
        print(f"AI enrichment failed: {e}")
        # Return original metadata if AI fails
        return table_metadata


def sync_external_tables(connection_id: int, selected_tables: List[Dict]) -> bool:
    """Sync selected tables metadata to local database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        connector = cm.get_connector(connection_id)
        
        for table_info in selected_tables:
            schema = table_info.get('schema', 'public')
            table_name = table_info['table_name']
            
            print(f"Syncing table: {schema}.{table_name}")
            
            # Get detailed metadata
            metadata = connector.get_table_metadata(schema, table_name)
            
            # Get sample data for AI enrichment
            try:
                sample_data = connector.get_sample_data(schema, table_name, limit=100)
                
                # Enrich with AI
                metadata = enrich_metadata_with_ai(metadata, sample_data)
            except Exception as e:
                print(f"Failed to get sample data or enrich: {e}")
                # Continue without AI enrichment
            
            # Create display name
            display_name = table_info.get('display_name', table_name)
            
            # Insert or update external table
            cursor.execute(f"""
                INSERT OR REPLACE INTO {EXTERNAL_TABLES_TABLE}
                (connection_id, schema_name, table_name, display_name, description, 
                 columns_metadata, row_count, last_synced, is_selected)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                connection_id,
                schema,
                table_name,
                display_name,
                metadata.get('description', ''),
                json.dumps(metadata.get('columns', [])),
                metadata.get('row_count', 0),
                datetime.now().isoformat(),
                1  # Mark as selected by default
            ))
        
        connector.disconnect()
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"Failed to sync tables: {str(e)}")
    finally:
        conn.close()


def get_external_tables(connection_id: int = None) -> List[Dict]:
    """Get all external tables, optionally filtered by connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if connection_id:
        cursor.execute(f"""
            SELECT et.*, c.connection_name, c.db_type
            FROM {EXTERNAL_TABLES_TABLE} et
            JOIN db_connections c ON et.connection_id = c.id
            WHERE et.connection_id = ?
            ORDER BY et.display_name
        """, (connection_id,))
    else:
        cursor.execute(f"""
            SELECT et.*, c.connection_name, c.db_type
            FROM {EXTERNAL_TABLES_TABLE} et
            JOIN db_connections c ON et.connection_id = c.id
            ORDER BY et.display_name
        """)
    
    tables = []
    for row in cursor.fetchall():
        table = dict(row)
        # Parse columns metadata
        if table.get('columns_metadata'):
            try:
                table['columns'] = json.loads(table['columns_metadata'])
            except:
                table['columns'] = []
        del table['columns_metadata']
        tables.append(table)
    
    conn.close()
    return tables


def delete_external_table(table_id: int) -> bool:
    """Delete an external table from local metadata by ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE id = ?", (table_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_external_table_by_name(table_name: str) -> bool:
    """Delete an external table from local metadata by display name or table name"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Try to delete by display_name first (what user sees), then by table_name
        cursor.execute(f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE display_name = ? OR table_name = ?",
                      (table_name, table_name))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_external_table_selection(table_id: int, is_selected: bool) -> bool:
    """Update whether an external table is selected for querying"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            UPDATE {EXTERNAL_TABLES_TABLE}
            SET is_selected = ?
            WHERE id = ?
        """, (is_selected, table_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def update_external_table_metadata(table_name: str, metadata: Dict) -> bool:
    """Update metadata for an external table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        columns_json = json.dumps(metadata.get('columns', []))
        
        cursor.execute(f"""
            UPDATE {EXTERNAL_TABLES_TABLE}
            SET description = ?, columns_metadata = ?
            WHERE table_name = ?
        """, (metadata.get('description', ''), columns_json, table_name))
        
        if cursor.rowcount == 0:
            return False
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to update external table metadata for {table_name}: {e}")
        raise e
    finally:
        conn.close()



def get_selected_external_tables() -> List[Dict]:
    """Get all selected external tables"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT et.*, c.connection_name, c.db_type
        FROM {EXTERNAL_TABLES_TABLE} et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.is_selected = 1
        ORDER BY et.display_name
    """)
    
    tables = []
    for row in cursor.fetchall():
        table = dict(row)
        if table.get('columns_metadata'):
            try:
                table['columns'] = json.loads(table['columns_metadata'])
            except:
                table['columns'] = []
        tables.append(table)
    
    conn.close()
    return tables

# Made with Bob
