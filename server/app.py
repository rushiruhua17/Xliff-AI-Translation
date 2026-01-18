from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import shutil
import os
import uuid
import sys

# Add project root to path to import core
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.parser import XliffParser
from core.abstractor import TagAbstractor
from core.validator import Validator
from ai.client import LLMClient

app = FastAPI()

# Allow CORS for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "server/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory session store (simple dict for MVP)
# SessionID -> { "parser": parser_obj, "units": [TranslationUnit], "abstractor": abstractor_obj }
# Note: XliffParser is not easily serializable, sticking to keeping objects in memory or re-parsing.
# For MVP simplicity: We will save the logical state.
sessions: Dict[str, Dict] = {}

class Segment(BaseModel):
    id: str
    source: str
    target: str
    state: str
    tags_map: Dict[str, str]

class TranslateRequest(BaseModel):
    session_id: str
    segment_ids: List[str]
    source_lang: str
    target_lang: str
    provider: str = "mock"

class UpdateSegmentRequest(BaseModel):
    session_id: str
    segment_id: str
    target_text: str

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        parser = XliffParser(file_path)
        parser.load()
        units = parser.get_translation_units()
        
        abstractor = TagAbstractor()
        parsed_segments = []
        
        for u in units:
            # Always re-abstract on load
            res = abstractor.abstract(u.source_raw)
            u.source_abstracted = res.abstracted_text
            u.tags_map = res.tags_map
            
            # If target exists and has tags, abstract it too? 
            # For MVP, if target is empty/new, we leave it empty.
            if u.target_raw and not u.target_abstracted:
                # Try simple abstraction on target, but might fail if tags mismatch source map.
                # For now assume target is empty or text-only for 'new' files.
                pass

            parsed_segments.append({
                "id": u.id,
                "source": u.source_abstracted,
                "target": u.target_abstracted,
                "state": u.state,
                "tags_map": u.tags_map
            })
            
        sessions[session_id] = {
            "file_path": file_path,
            "units": units, # Note: objects are mutable reference
            "filename": file.filename
        }
        
        return {"session_id": session_id, "segments": parsed_segments, "filename": file.filename}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/translate")
async def translate_segments(req: TranslateRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions[req.session_id]
    units = session["units"]
    units_map = {u.id: u for u in units}
    
    # Prepare batch
    batch_data = []
    for seg_id in req.segment_ids:
        if seg_id in units_map:
            u = units_map[seg_id]
            batch_data.append({"id": u.id, "text": u.source_abstracted})
            
    if not batch_data:
        return {"results": []}

    # Call AI
    client = LLMClient(provider=req.provider)
    ai_results = client.translate_batch(batch_data, req.source_lang, req.target_lang)
    
    # Update Session Data & Validate
    validator = Validator()
    
    response_data = []
    for res in ai_results:
        uid = res["id"]
        translation = res["translation"]
        
        if uid in units_map:
            u = units_map[uid]
            u.target_abstracted = translation
            u.state = "translated"
            
            errors = validator.validate_structure(u)
            
            response_data.append({
                "id": uid,
                "target": translation,
                "errors": errors
            })
            
    return {"results": response_data}

@app.post("/api/export")
async def export_file(session_id: str, segments: List[Segment]):
    """
    Receives current state from frontend (in case of manual edits), reconstructs and returns file.
    Wait, exporting usually just needs session_id if we keep state in sync.
    But frontend might have manual edits.
    Let's trust backend state for now, assuming /api/update was called or we accept full payload.
    Better: Accept updates here.
    """
    # Simply using backend state for MVP specific export
    # Or strict: Frontend sends all segments final state.
    # Let's use backend state. Frontend should sync updates via another endpoint or we accept partials here?
    pass

@app.post("/api/update_segment")
async def update_segment(req: UpdateSegmentRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[req.session_id]
    units = session["units"]
    
    target_unit = next((u for u in units if u.id == req.segment_id), None)
    if target_unit:
        target_unit.target_abstracted = req.target_text
        return {"status": "ok"}
    return {"status": "error", "message": "Segment not found"}

@app.get("/api/download/{session_id}")
async def download_file(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions[session_id]
    units = session["units"]
    original_path = session["file_path"]
    filename = session["filename"]
    
    # Reconstruct
    abstractor = TagAbstractor()
    reconstruction_errors = []
    
    for u in units:
        if u.target_abstracted:
            try:
                u.target_raw = abstractor.reconstruct(u.target_abstracted, u.tags_map)
            except Exception as e:
                reconstruction_errors.append(f"Unit {u.id}: {str(e)}")
                # Fallback? Keep empty or raw
                
    # Save to temp
    output_filename = f"translated_{filename}"
    output_path = os.path.join(UPLOAD_DIR, f"{session_id}_{output_filename}")
    
    parser = XliffParser(original_path)
    parser.load() # Reload to get clean tree
    parser.update_targets(units, output_path)
    
    from fastapi.responses import FileResponse
    return FileResponse(output_path, filename=output_filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
