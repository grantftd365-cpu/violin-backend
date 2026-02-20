from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
import time
from pathlib import Path
from services.youtube_service import YoutubeService
from services.transcription_service import TranscriptionService
from services.recognition_service import RecognitionService
from duckduckgo_search import DDGS
from fastapi import Request
import gc

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

# Initialize services
youtube_service = YoutubeService(download_dir=str(TEMP_DIR))
transcription_service = TranscriptionService()
recognition_service = RecognitionService()

class TranscriptionRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Violin Sheet Generator API"}

@app.post("/transcribe/upload")
async def transcribe_upload(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio file directly.
    Bypasses YouTube/Bilibili download entirely.
    """
    audio_path = None
    midi_path = None
    xml_path = None
    
    try:
        print(f"[MEMORY] Starting upload transcription for: {file.filename}")
        gc.collect()
        
        # Validate file type
        allowed_extensions = {
            # Audio
            '.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma',
            # Video (ffmpeg will extract audio)
            '.mp4', '.mov', '.avi', '.webm', '.mkv'
        }
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Save uploaded file
        audio_filename = f"upload_{int(time.time())}{file_ext}"
        audio_path = TEMP_DIR / audio_filename
        
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = audio_path.stat().st_size
        print(f"[MEMORY] Saved uploaded file: {audio_path} ({file_size} bytes)")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        # STEP 1: Try to identify the song
        print(f"[RECOGNITION] Attempting to identify song...")
        song_metadata = recognition_service.identify_song(audio_path)
        is_recognized = False
        recognition_msg = ""

        if song_metadata:
            is_recognized = True
            recognition_msg = f"Identified: {song_metadata['title']} by {song_metadata['artist']}"
            print(f"[RECOGNITION] {recognition_msg}")
            
            # STEP 2: Auto-search for sheet music using the identified title
            search_keyword = f"{song_metadata['title']} {song_metadata['artist']} violin"
            # We can't call search_imslp directly because it expects a Request object
            # But we can reuse the logic or just let the frontend trigger the search
            # Better: Return the search query to frontend so it can open Bing
            recognition_msg += f"\n(Tip: Click 'Search Web' to find standard score)"
            
        else:
            print("[RECOGNITION] Song not recognized, using AI transcription")

        # 1. Transcribe to MIDI (AI Fallback)
        midi_filename = audio_path.stem + ".mid"
        midi_path = TEMP_DIR / midi_filename
        print(f"[MEMORY] Transcribing to MIDI: {midi_path}")
        
        midi_result = transcription_service.transcribe_audio_to_midi(audio_path, midi_path)
        if not midi_result:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio to MIDI")
        
        print(f"[MEMORY] MIDI generation complete")
        
        # 2. Convert to MusicXML
        xml_filename = audio_path.stem + ".musicxml"
        xml_path = TEMP_DIR / xml_filename
        print(f"[MEMORY] Converting to MusicXML: {xml_path}")
        
        xml_result = transcription_service.convert_midi_to_musicxml(midi_path, xml_path)
        if not xml_result:
            raise HTTPException(status_code=500, detail="Failed to convert MIDI to MusicXML")
        
        print(f"[MEMORY] XML generation complete")
        
        # 3. Read content
        if not xml_path.exists():
            print(f"ERROR: XML file missing at {xml_path}")
            raise HTTPException(status_code=500, detail="XML file generation failed")
        
        with open(xml_path, "r", encoding="utf-8") as f:
            musicxml_content = f.read()
        
        print(f"[MEMORY] Generated XML size: {len(musicxml_content)} bytes")
        
        if len(musicxml_content) == 0:
            print("ERROR: Generated XML is empty!")
            raise HTTPException(status_code=500, detail="Generated XML is empty")
        
        return {"musicxml": musicxml_content}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[MEMORY] Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")
    
    finally:
        # Cleanup
        print("[MEMORY] Starting cleanup...")
        try:
            if 'audio_path' in locals() and audio_path and audio_path.exists():
                os.remove(audio_path)
            if 'midi_path' in locals() and midi_path and midi_path.exists():
                os.remove(midi_path)
            if 'xml_path' in locals() and xml_path and xml_path.exists():
                os.remove(xml_path)
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")
        
        gc.collect()
        print("[MEMORY] Cleanup complete")

@app.post("/search/imslp")
async def search_imslp(request: Request):
    """
    Search IMSLP for standard sheet music PDFs.
    Uses Google search with site:imslp.org filter.
    """
    try:
        body = await request.json()
        keyword = body.get('keyword', '').strip()
        
        if not keyword:
            raise HTTPException(status_code=400, detail="Search keyword is required")
        
        # Construct search query
        search_query = f"site:imslp.org {keyword} violin pdf"
        print(f"[IMSLP SEARCH] Query: {search_query}")
        
        # Perform DuckDuckGo search (more reliable than Google for bots)
        results = []
        try:
            with DDGS() as ddgs:
                ddg_results = ddgs.text(search_query, max_results=5)
                for r in ddg_results:
                    # DDGS returns {'title': ..., 'href': ..., 'body': ...}
                    title = r.get('title', 'Unknown Title').replace(' - IMSLP', '')
                    link = r.get('href', '')
                    if link:
                        results.append({
                            "title": title,
                            "link": link
                        })
        except Exception as search_err:
            print(f"[IMSLP SEARCH] DDG search error: {search_err}")
            # Return empty list instead of crashing
            return {"results": []}
        
        print(f"[IMSLP SEARCH] Found {len(results)} results")
        return {"results": results}
        
    except Exception as e:
        print(f"[IMSLP SEARCH] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
