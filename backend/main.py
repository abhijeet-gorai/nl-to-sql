from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
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

app = FastAPI()

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


class ChatRequest(BaseModel):
    message: str
    selected_tables: List[str] = []
    thread_id: str = "default"


class RegisterRequest(BaseModel):
    file_path: str
    metadata: Dict[str, Any]


@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    # Save to temp file
    temp_filename = f"temp_{uuid.uuid4()}.csv"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Basic analysis (Pandas)
        db_result = db.analyze_csv(temp_filename, file.filename)

        # AI Enrichment
        try:
            # Get existing table names to avoid collisions
            tables = db.get_all_tables()
            existing_names = [t["table_name"] for t in tables]

            ai_metadata = agent.generate_table_metadata(
                db_result, file.filename, existing_names
            )

            # Merge AI Suggestions
            db_result["suggested_table_name"] = ai_metadata.get(
                "table_name", db_result["suggested_table_name"]
            )
            db_result["description"] = ai_metadata.get(
                "description", db_result["description"]
            )

            # Merge Column Descriptions
            ai_cols = {
                c["name"]: c.get("description", "")
                for c in ai_metadata.get("columns", [])
            }
            for col in db_result["columns"]:
                if col["name"] in ai_cols:
                    col["description"] = ai_cols[col["name"]]

            # Ensure uniqueness
            proposed_name = db_result["suggested_table_name"]
            if db.check_table_exists(proposed_name):
                # If exists, append random suffix
                suffix = db.generate_random_suffix()
                db_result["suggested_table_name"] = f"{proposed_name}_{suffix}"

        except Exception as e:
            print(f"AI enrichment failed, proceeding with basic analysis: {e}")
            # Even for basic analysis, ensure uniqueness if we use the default fallback
            # (Note: db.analyze_csv already called generate_table_name which adds a suffix by default,
            # so we are mostly covered, but good to be safe if logic changes)

        return db_result
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register")
async def register_table(request: RegisterRequest):
    try:
        success = db.register_table(request.file_path, request.metadata)

        # Cleanup temp file
        if os.path.exists(request.file_path):
            os.remove(request.file_path)

        return {"status": success, "table_name": request.metadata["table_name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateMetadataRequest(BaseModel):
    metadata: Dict[str, Any]


@app.put("/tables/{table_name}")
async def update_table(
    table_name: str,
    request: UpdateMetadataRequest,
    source_type: Optional[str] = None,
    connection_id: Optional[int] = None,
    schema: Optional[str] = None,
):
    try:
        # If source_type is specified, be strict about it
        if source_type == "csv":
            success = db.update_table_metadata(table_name, request.metadata)
            if not success:
                raise HTTPException(status_code=404, detail="CSV table not found")
        elif source_type == "external":
            success = me.update_external_table_metadata(
                table_name, request.metadata, connection_id=connection_id, schema=schema
            )
            if not success:
                raise HTTPException(status_code=404, detail="External table not found")
        else:
            # Fallback for backward compatibility (try CSV first, then external)
            success = db.update_table_metadata(table_name, request.metadata)
            if not success:
                # If not found in CSV tables, try external tables (heuristic match by name)
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


# ============================================
# Connection Management Endpoints
# ============================================


class ConnectionCreate(BaseModel):
    connection_name: str
    db_type: str  # 'postgresql', 'db2', 'mysql', 'oracle'
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


class TableSyncRequest(BaseModel):
    tables: List[Dict]  # [{"schema": "public", "table_name": "customers"}, ...]


@app.post("/connections")
async def create_connection(connection: ConnectionCreate):
    """Create a new database connection"""
    try:
        connection_id = cm.create_connection(connection.dict())
        return {"status": "success", "connection_id": connection_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/connections")
async def list_connections():
    """List all database connections"""
    return cm.get_all_connections()


@app.get("/connections/{connection_id}")
async def get_connection_details(connection_id: int):
    """Get connection details (without password)"""
    connection = cm.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    # Don't return password
    connection.pop("password", None)
    return connection


@app.put("/connections/{connection_id}")
async def update_connection(connection_id: int, update: ConnectionUpdate):
    """Update an existing connection"""
    try:
        success = cm.update_connection(connection_id, update.dict(exclude_unset=True))
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/connections/{connection_id}")
async def delete_connection(connection_id: int):
    """Delete a database connection"""
    success = cm.delete_connection(connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "success"}


@app.post("/connections/{connection_id}/test")
async def test_connection(connection_id: int):
    """Test a database connection"""
    result = cm.test_connection(connection_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/connections/test")
async def test_connection_data(connection: ConnectionCreate):
    """Test connection without saving it"""
    result = cm.test_connection_data(connection.dict())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ============================================
# Table Discovery Endpoints
# ============================================


@app.get("/connections/{connection_id}/schemas")
async def list_schemas(connection_id: int):
    """List all schemas in a database"""
    try:
        connector = cm.get_connector(connection_id)
        schemas = connector.get_schemas()
        connector.disconnect()
        return {"schemas": schemas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connections/{connection_id}/tables")
async def list_tables(connection_id: int, schema: str = None):
    """List all tables in a schema"""
    try:
        tables = me.discover_tables(connection_id, schema)
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connections/{connection_id}/tables/{table_name}")
async def get_table_metadata_endpoint(
    connection_id: int, table_name: str, schema: str = "public"
):
    """Get detailed metadata for a table"""
    try:
        metadata = me.extract_table_metadata(connection_id, schema, table_name)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/connections/{connection_id}/tables/sync")
async def sync_tables(connection_id: int, request: TableSyncRequest):
    """Sync selected tables from external database"""
    try:
        success = me.sync_external_tables(connection_id, request.tables)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sync tables")

        # Get the synced tables with their metadata
        synced_tables = me.get_external_tables(connection_id)
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


@app.get("/connections/{connection_id}/tables/{table_name}/preview")
async def preview_table(
    connection_id: int, table_name: str, schema: str = "public", limit: int = 100
):
    """Preview data from a table"""
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


@app.get("/external-tables")
async def list_external_tables(connection_id: Optional[int] = None):
    """List all external tables"""
    return me.get_external_tables(connection_id)


@app.get("/tables")
async def get_tables():
    """Get all available tables (CSV + External)"""
    return query_router.get_all_available_tables()


@app.delete("/tables/{table_name}")
async def delete_table(
    table_name: str,
    source_type: Optional[str] = None,
    connection_id: Optional[int] = None,
    schema: Optional[str] = None,
):
    try:
        if source_type == "csv":
            success = db.delete_table(table_name)
            if not success:
                raise HTTPException(status_code=404, detail="CSV table not found")
        elif source_type == "external":
            success = me.delete_external_table_composite(
                table_name, connection_id=connection_id, schema=schema
            )
            if not success:
                raise HTTPException(status_code=404, detail="External table not found")
        else:
            # Fallback legacy behavior
            success = db.delete_table(table_name)
            if not success:
                success = me.delete_external_table_by_name(table_name)
                if not success:
                    raise HTTPException(status_code=404, detail="Table not found")

        return {"status": "success", "table_name": table_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        return StreamingResponse(
            agent.stream_question(
                request.message, request.selected_tables, request.thread_id
            ),
            media_type="application/x-ndjson",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "ok"}
