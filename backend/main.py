from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import shutil
import os
import uuid
# Import our local modules
import db, agent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
@app.on_event("startup")
async def startup_event():
    db.init_db()

class ChatRequest(BaseModel):
    message: str
    selected_tables: List[str] = []
    thread_id: str = "default"

class RegisterRequest(BaseModel):
    file_path: str
    metadata: Dict[str, Any]

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
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
            ai_metadata = agent.generate_table_metadata(db_result, file.filename)
            
            # Merge AI Suggestions
            db_result["suggested_table_name"] = ai_metadata.get("table_name", db_result["suggested_table_name"])
            db_result["description"] = ai_metadata.get("description", db_result["description"])
            
            # Merge Column Descriptions
            ai_cols = {c["name"]: c.get("description", "") for c in ai_metadata.get("columns", [])}
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
            
        return {"status": "success", "table_name": request.metadata['table_name']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tables")
async def get_tables():
    return db.get_all_tables()

@app.delete("/tables/{table_name}")
async def delete_table(table_name: str):
    success = db.delete_table(table_name)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete table")
    return {"status": "success", "table_name": table_name}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        return StreamingResponse(
            agent.stream_question(request.message, request.selected_tables, request.thread_id),
            media_type="application/x-ndjson"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
