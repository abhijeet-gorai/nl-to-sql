"""
Metadata Extractor Module
Discovers and enriches metadata from external databases
"""

import json
from typing import List, Dict
import pandas as pd
from datetime import datetime, date
import connection_manager as cm
import agent

from database_config import get_connection, get_transaction, execute, fetch, fetchrow

EXTERNAL_TABLES_TABLE = "external_tables"


async def discover_tables(connection_id: int, schema: str = None) -> List[Dict]:
    """Discover all tables in a schema"""
    try:
        connector = await cm.get_connector_async(connection_id)

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


async def extract_table_metadata(connection_id: int, schema: str, table: str) -> Dict:
    """Extract detailed metadata for a specific table"""
    try:
        connector = await cm.get_connector_async(connection_id)
        metadata = connector.get_table_metadata(schema, table)
        connector.disconnect()

        return metadata
    except Exception as e:
        raise Exception(f"Failed to extract table metadata: {str(e)}")


async def enrich_metadata_with_ai(table_metadata: Dict, sample_data: pd.DataFrame) -> Dict:
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
            "columns": table_metadata["columns"],
        }

        # Use existing AI metadata generation (now async)
        table_name = table_metadata["table_name"]
        enriched, _ = await agent.generate_table_metadata(
            preview_data,
            table_name,
            [],  # No need to check existing names for external tables
        )

        # Merge AI descriptions with existing metadata
        if enriched:
            table_metadata["description"] = enriched.get(
                "description", table_metadata.get("description", "")
            )

            # Update column descriptions
            ai_cols = {
                c["name"]: c.get("description", "") for c in enriched.get("columns", [])
            }
            for col in table_metadata["columns"]:
                if col["name"] in ai_cols and ai_cols[col["name"]]:
                    col["description"] = ai_cols[col["name"]]

        return table_metadata

    except Exception as e:
        print(f"AI enrichment failed: {e}")
        # Return original metadata if AI fails
        return table_metadata


async def sync_external_tables(
    connection_id: int, selected_tables: List[Dict], project_id: int = None
) -> bool:
    """Sync selected tables metadata to local database"""
    async with get_transaction() as conn:
        try:
            connector = await cm.get_connector_async(connection_id)

            for table_info in selected_tables:
                schema = table_info.get("schema", "public")
                table_name = table_info["table_name"]

                print(f"Syncing table: {schema}.{table_name}")

                # Get detailed metadata
                metadata = connector.get_table_metadata(schema, table_name)

                # Get sample data for AI enrichment
                try:
                    sample_data = connector.get_sample_data(schema, table_name, limit=100)

                    # Enrich with AI (now async)
                    metadata = await enrich_metadata_with_ai(metadata, sample_data)
                except Exception as e:
                    print(f"Failed to get sample data or enrich: {e}")
                    # Continue without AI enrichment

                # Create display name
                display_name = table_info.get("display_name", table_name)

                # Insert or update external table (PostgreSQL UPSERT)
                await conn.execute(
                    f"""
                    INSERT INTO {EXTERNAL_TABLES_TABLE}
                    (connection_id, schema_name, table_name, display_name, description, 
                     columns_metadata, row_count, last_synced, is_selected, project_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (connection_id, schema_name, table_name) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        columns_metadata = EXCLUDED.columns_metadata,
                        row_count = EXCLUDED.row_count,
                        last_synced = EXCLUDED.last_synced,
                        is_selected = EXCLUDED.is_selected,
                        project_id = EXCLUDED.project_id
                    """,
                    connection_id,
                    schema,
                    table_name,
                    display_name,
                    metadata.get("description", ""),
                    json.dumps(metadata.get("columns", [])),
                    metadata.get("row_count", 0),
                    datetime.now(),
                    True,  # Mark as selected by default
                    project_id,
                )

            connector.disconnect()
            return True

        except Exception as e:
            raise Exception(f"Failed to sync tables: {str(e)}")


async def get_external_tables(
    connection_id: int = None, project_id: int = None
) -> List[Dict]:
    """Get all external tables, optionally filtered by connection and/or project"""
    query = f"""
        SELECT et.*, c.connection_name, c.db_type
        FROM {EXTERNAL_TABLES_TABLE} et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE 1=1
    """
    params = []
    param_num = 1

    if connection_id is not None:
        query += f" AND et.connection_id = ${param_num}"
        params.append(connection_id)
        param_num += 1

    if project_id is not None:
        query += f" AND et.project_id = ${param_num}"
        params.append(project_id)
        param_num += 1

    query += " ORDER BY et.display_name"

    rows = await fetch(query, *params)

    tables = []
    for row in rows:
        table = dict(row)
        # Parse columns metadata
        if table.get("columns_metadata"):
            try:
                table["columns"] = json.loads(table["columns_metadata"])
            except:
                table["columns"] = []
        if "columns_metadata" in table:
            del table["columns_metadata"]
        tables.append(table)

    return tables


async def delete_external_table(table_id: int) -> bool:
    """Delete an external table from local metadata by ID"""
    result = await execute(f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE id = $1", table_id)
    return "DELETE" in result


async def delete_external_table_by_name(table_name: str) -> bool:
    """Delete an external table from local metadata by display name or table name"""
    result = await execute(
        f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE display_name = $1 OR table_name = $1",
        table_name
    )
    return "DELETE" in result


async def update_external_table_selection(table_id: int, is_selected: bool) -> bool:
    """Update whether an external table is selected for querying"""
    result = await execute(
        f"""
        UPDATE {EXTERNAL_TABLES_TABLE}
        SET is_selected = $1
        WHERE id = $2
        """,
        is_selected, table_id
    )
    return "UPDATE" in result


async def update_external_table_metadata(
    table_name: str, metadata: Dict, connection_id: int = None, schema: str = None
) -> bool:
    """Update metadata for an external table"""
    try:
        columns_json = json.dumps(metadata.get("columns", []))

        # Build query and params based on available identifiers
        query = f"UPDATE {EXTERNAL_TABLES_TABLE} SET description = $1, columns_metadata = $2 WHERE table_name = $3"
        params = [metadata.get("description", ""), columns_json, table_name]
        param_num = 4

        if connection_id is not None:
            query += f" AND connection_id = ${param_num}"
            params.append(connection_id)
            param_num += 1

        if schema is not None:
            query += f" AND schema_name = ${param_num}"
            params.append(schema)

        result = await execute(query, *params)
        return "UPDATE" in result

    except Exception as e:
        print(f"Failed to update external table metadata for {table_name}: {e}")
        raise e


async def delete_external_table_composite(
    table_name: str, connection_id: int = None, schema: str = None
) -> bool:
    """Delete an external table using composite keys (safer than just name)"""
    query = f"DELETE FROM {EXTERNAL_TABLES_TABLE} WHERE table_name = $1"
    params = [table_name]
    param_num = 2

    if connection_id is not None:
        query += f" AND connection_id = ${param_num}"
        params.append(connection_id)
        param_num += 1

    if schema is not None:
        query += f" AND schema_name = ${param_num}"
        params.append(schema)

    result = await execute(query, *params)
    return "DELETE" in result


async def get_selected_external_tables() -> List[Dict]:
    """Get all selected external tables"""
    rows = await fetch(f"""
        SELECT et.*, c.connection_name, c.db_type
        FROM {EXTERNAL_TABLES_TABLE} et
        JOIN db_connections c ON et.connection_id = c.id
        WHERE et.is_selected = TRUE
        ORDER BY et.display_name
    """)

    tables = []
    for row in rows:
        table = dict(row)
        if table.get("columns_metadata"):
            try:
                table["columns"] = json.loads(table["columns_metadata"])
            except:
                table["columns"] = []
        tables.append(table)

    return tables
