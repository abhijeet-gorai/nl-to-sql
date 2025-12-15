from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    thread_id: str = "default"

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    # Save to temp file
    temp_filename = f"temp_{uuid.uuid4()}.csv"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process CSV
        # We use strict table name "uploaded_data" for simplicity in this demo,
        # or we could make it dynamic based on filename.
        result = db.process_csv(temp_filename, table_name="uploaded_data")
        
        # Cleanup
        os.remove(temp_filename)
        
        return {"message": "File processed successfully", "schema": result, "table_name": "uploaded_data"}
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        result = agent.process_question(request.message, request.thread_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
