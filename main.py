from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path

app = FastAPI(title="Violin Sheet Generator")

# CORS for frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Violin Sheet Generator API"}

@app.post("/generate-from-url")
async def generate_from_url(youtube_url: str):
    """
    1. Download audio from YouTube
    2. Transcribe using Basic Pitch
    3. Convert to MusicXML using Music21
    4. Return MusicXML content
    """
    # Placeholder for logic
    return {"message": "Not implemented yet", "url": youtube_url}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
