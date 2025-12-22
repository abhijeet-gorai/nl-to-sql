from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import shutil
import os
import uuid

# Import our local modules
import db
import agent
import connection_manager as cm
import metadata_extractor as me
import query_router
import auth
import projects
from dependencies import (
    require_read_access,
    require_write_access,
)
from routers import auth_router, projects_router

app = FastAPI(
    title="NL-to-SQL API",
    description="Natural Language to SQL with project-based access control",
    version="2.0.0",
)

from fastapi.staticfiles import StaticFiles

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create charts directory if not exists
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# Mount static files for charts
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")


# Initialize DB on startup
@app.on_event("startup")
async def startup_event():
    db.init_db()
    cm.init_connections_table()
    auth.init_users_table()
    projects.init_projects_tables()


# Include routers
app.include_router(auth_router.router)
app.include_router(projects_router.router)


# ============================================
# Request/Response Models
# ============================================


class TableSelection(BaseModel):
    table_name: str
    source_type: str = "csv"  # 'csv' or 'external'
    connection_id: Optional[int] = None
    schema: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    selected_tables: List[TableSelection] = []
    thread_id: str = "default"


class RegisterRequest(BaseModel):
    file_path: str
    metadata: Dict[str, Any]


class UpdateMetadataRequest(BaseModel):
    metadata: Dict[str, Any]


class TableSyncRequest(BaseModel):
    tables: List[Dict]  # [{"schema": "public", "table_name": "customers"}, ...]


class ConnectionCreate(BaseModel):
    connection_name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_enabled: bool = False
    connection_params: Dict = {}


class ConnectionUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


# ============================================
# Project-Scoped Table Endpoints
# ============================================


@app.post("/projects/{project_id}/analyze")
async def analyze_file_project(
    project_id: int,
    file: UploadFile = File(...),
    access: dict = Depends(require_write_access),
):
    """Analyze a CSV file (project-scoped, requires write access)"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    temp_filename = f"temp_{uuid.uuid4()}.csv"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_result = db.analyze_csv(temp_filename, file.filename)

        try:
            tables = db.get_all_tables(project_id)
            existing_names = [t["table_name"] for t in tables]

            ai_metadata = agent.generate_table_metadata(
                db_result, file.filename, existing_names
            )

            db_result["suggested_table_name"] = ai_metadata.get(
                "table_name", db_result["suggested_table_name"]
            )
            db_result["description"] = ai_metadata.get(
                "description", db_result["description"]
            )

            ai_cols = {
                c["name"]: c.get("description", "")
                for c in ai_metadata.get("columns", [])
            }
            for col in db_result["columns"]:
                if col["name"] in ai_cols:
                    col["description"] = ai_cols[col["name"]]

            proposed_name = db_result["suggested_table_name"]
            if db.check_table_exists(proposed_name, project_id):
                suffix = db.generate_random_suffix()
                db_result["suggested_table_name"] = f"{proposed_name}_{suffix}"

        except Exception as e:
            print(f"AI enrichment failed, proceeding with basic analysis: {e}")

        return db_result
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects/{project_id}/tables/register")
async def register_table_project(
    project_id: int,
    request: RegisterRequest,
    access: dict = Depends(require_write_access),
):
    """Register a table in a project (requires write access)"""
    try:
        success = db.register_table(request.file_path, request.metadata, project_id)

        if os.path.exists(request.file_path):
            os.remove(request.file_path)

        return {"status": success, "table_name": request.metadata["table_name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/{project_id}/tables")
async def get_project_tables(
    project_id: int, access: dict = Depends(require_read_access)
):
    """Get all tables in a project (requires read access)"""
    return query_router.get_all_available_tables(project_id)


@app.put("/projects/{project_id}/tables/{table_name}")
async def update_project_table(
    project_id: int,
    table_name: str,
    request: UpdateMetadataRequest,
    source_type: Optional[str] = None,
    connection_id: Optional[int] = None,
    schema: Optional[str] = None,
    access: dict = Depends(require_write_access),
):
    """Update table metadata in a project (requires write access)"""
    try:
        if source_type == "csv":
            success = db.update_table_metadata(table_name, request.metadata, project_id)
            if not success:
                raise HTTPException(status_code=404, detail="CSV table not found")
        elif source_type == "external":
            success = me.update_external_table_metadata(
                table_name, request.metadata, connection_id=connection_id, schema=schema
            )
            if not success:
                raise HTTPException(status_code=404, detail="External table not found")
        else:
            success = db.update_table_metadata(table_name, request.metadata, project_id)
            if not success:
                success = me.update_external_table_metadata(
                    table_name, request.metadata
                )
                if not success:
                    raise HTTPException(status_code=404, detail="Table not found")

        return {"status": "success", "table_name": table_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/projects/{project_id}/tables/{table_name}")
async def delete_project_table(
    project_id: int,
    table_name: str,
    source_type: Optional[str] = None,
    connection_id: Optional[int] = None,
    schema: Optional[str] = None,
    access: dict = Depends(require_write_access),
):
    """Delete a table from a project (requires write access)"""
    try:
        if source_type == "csv":
            success = db.delete_table(table_name, project_id)
            if not success:
                raise HTTPException(status_code=404, detail="CSV table not found")
        elif source_type == "external":
            success = me.delete_external_table_composite(
                table_name, connection_id=connection_id, schema=schema
            )
            if not success:
                raise HTTPException(status_code=404, detail="External table not found")
        else:
            success = db.delete_table(table_name, project_id)
            if not success:
                success = me.delete_external_table_by_name(table_name)
                if not success:
                    raise HTTPException(status_code=404, detail="Table not found")

        return {"status": "success", "table_name": table_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Project-Scoped Connection Endpoints
# ============================================


@app.post("/projects/{project_id}/connections")
async def create_connection_project(
    project_id: int,
    connection: ConnectionCreate,
    access: dict = Depends(require_write_access),
):
    """Create a new database connection in a project (requires write access)"""
    try:
        connection_id = cm.create_connection(connection.dict(), project_id)
        return {"status": "success", "connection_id": connection_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/projects/{project_id}/connections")
async def list_connections_project(
    project_id: int, access: dict = Depends(require_read_access)
):
    """List all connections in a project (requires read access)"""
    return cm.get_all_connections(project_id)


@app.get("/projects/{project_id}/connections/{connection_id}")
async def get_connection_project(
    project_id: int, connection_id: int, access: dict = Depends(require_read_access)
):
    """Get connection details in a project (requires read access)"""
    connection = cm.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    # Verify connection belongs to this project
    if connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )
    connection.pop("password", None)
    return connection


@app.put("/projects/{project_id}/connections/{connection_id}")
async def update_connection_project(
    project_id: int,
    connection_id: int,
    update: ConnectionUpdate,
    access: dict = Depends(require_write_access),
):
    """Update a connection in a project (requires write access)"""
    # Verify connection belongs to this project first
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        success = cm.update_connection(connection_id, update.dict(exclude_unset=True))
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/projects/{project_id}/connections/{connection_id}")
async def delete_connection_project(
    project_id: int, connection_id: int, access: dict = Depends(require_write_access)
):
    """Delete a connection from a project (requires write access)"""
    # Verify connection belongs to this project first
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    success = cm.delete_connection(connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success"}


@app.post("/projects/{project_id}/connections/{connection_id}/test")
async def test_connection_project(
    project_id: int, connection_id: int, access: dict = Depends(require_write_access)
):
    """Test a database connection (requires write access)"""
    # Verify connection belongs to this project first
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    result = cm.test_connection(connection_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/projects/{project_id}/connections/test")
async def test_connection_data_project(
    project_id: int,
    connection: ConnectionCreate,
    access: dict = Depends(require_write_access),
):
    """Test connection without saving it (requires write access)"""
    result = cm.test_connection_data(connection.dict())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ============================================
# Project-Scoped Table Discovery Endpoints
# ============================================


@app.get("/projects/{project_id}/connections/{connection_id}/schemas")
async def list_schemas_project(
    project_id: int, connection_id: int, access: dict = Depends(require_read_access)
):
    """List all schemas in a database (requires read access)"""
    # Verify connection belongs to this project
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        connector = cm.get_connector(connection_id)
        schemas = connector.get_schemas()
        connector.disconnect()
        return {"schemas": schemas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/{project_id}/connections/{connection_id}/tables")
async def list_tables_project(
    project_id: int,
    connection_id: int,
    schema: str = None,
    access: dict = Depends(require_read_access),
):
    """List all tables in a schema (requires read access)"""
    # Verify connection belongs to this project
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        tables = me.discover_tables(connection_id, schema)
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/{project_id}/connections/{connection_id}/tables/{table_name}")
async def get_table_metadata_project(
    project_id: int,
    connection_id: int,
    table_name: str,
    schema: str = "public",
    access: dict = Depends(require_read_access),
):
    """Get detailed metadata for a table (requires read access)"""
    # Verify connection belongs to this project
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        metadata = me.extract_table_metadata(connection_id, schema, table_name)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects/{project_id}/connections/{connection_id}/tables/sync")
async def sync_tables_project(
    project_id: int,
    connection_id: int,
    request: TableSyncRequest,
    access: dict = Depends(require_write_access),
):
    """Sync tables from external database (requires write access)"""
    # Verify connection belongs to this project
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        success = me.sync_external_tables(connection_id, request.tables, project_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sync tables")

        synced_tables = me.get_external_tables(connection_id, project_id)
        synced_table_names = [t["table_name"] for t in request.tables]
        synced_tables = [
            t for t in synced_tables if t["table_name"] in synced_table_names
        ]

        return {
            "status": "success",
            "synced_count": len(request.tables),
            "tables": synced_tables,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/projects/{project_id}/connections/{connection_id}/tables/{table_name}/preview"
)
async def preview_table_project(
    project_id: int,
    connection_id: int,
    table_name: str,
    schema: str = "public",
    limit: int = 100,
    access: dict = Depends(require_read_access),
):
    """Preview data from a table (requires read access)"""
    # Verify connection belongs to this project
    connection = cm.get_connection(connection_id)
    if not connection or connection.get("project_id") != project_id:
        raise HTTPException(
            status_code=404, detail="Connection not found in this project"
        )

    try:
        connector = cm.get_connector(connection_id)
        df = connector.get_sample_data(schema, table_name, limit)
        connector.disconnect()

        return {
            "columns": df.columns.tolist(),
            "data": df.fillna("").to_dict(orient="records"),
            "row_count": len(df),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/{project_id}/external-tables")
async def list_external_tables_project(
    project_id: int,
    connection_id: Optional[int] = None,
    access: dict = Depends(require_read_access),
):
    """List external tables in a project (requires read access)"""
    return me.get_external_tables(connection_id, project_id)


# ============================================
# Project-Scoped Chat Endpoint
# ============================================


@app.post("/projects/{project_id}/chat")
async def chat_project(
    project_id: int, request: ChatRequest, access: dict = Depends(require_read_access)
):
    """Chat with tables in a project (requires read access)"""
    try:
        # Security check: Verify all selected tables belong to this project
        if request.selected_tables:
            # Get all tables available in this project
            project_tables = query_router.get_all_available_tables(project_id)

            # Build a set of valid table identifiers (composite key)
            # For CSV: (table_name, "csv", None, None)
            # For External: (table_name, "external", connection_id, schema_name)
            valid_table_keys = set()
            for t in project_tables:
                key = (
                    t["table_name"],
                    t.get("source_type", "csv"),
                    t.get("connection_id"),
                    t.get("schema_name"),
                )
                valid_table_keys.add(key)

            # Check each selected table using composite key
            for table in request.selected_tables:
                selected_key = (
                    table.table_name,
                    table.source_type,
                    table.connection_id,
                    table.schema,
                )
                if selected_key not in valid_table_keys:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Table '{table.table_name}' with the specified source is not available in this project",
                    )

        return StreamingResponse(
            agent.stream_question(
                request.message, request.selected_tables, request.thread_id
            ),
            media_type="application/x-ndjson",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Health Check
# ============================================


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
