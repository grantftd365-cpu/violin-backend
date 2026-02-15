from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
from pathlib import Path
from services.youtube_service import YoutubeService
from services.transcription_service import TranscriptionService

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

class TranscriptionRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Violin Sheet Generator API"}

@app.post("/transcribe/youtube")
async def transcribe_youtube(request: TranscriptionRequest):
    """
    1. Download audio from YouTube
    2. Transcribe using Basic Pitch
    3. Convert to MusicXML using Music21
    4. Return MusicXML content
    """
    try:
        # 1. Download
        print(f"Downloading audio from: {request.url}")
        audio_path = youtube_service.download_audio(request.url)
        if not audio_path:
            raise HTTPException(status_code=400, detail="Failed to download audio from YouTube")

        # 2. Transcribe to MIDI
        midi_filename = audio_path.stem + ".mid"
        midi_path = TEMP_DIR / midi_filename
        print(f"Transcribing to MIDI: {midi_path}")
        
        midi_result = transcription_service.transcribe_audio_to_midi(audio_path, midi_path)
        if not midi_result:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio to MIDI")

        # 3. Convert to MusicXML
        xml_filename = audio_path.stem + ".musicxml"
        xml_path = TEMP_DIR / xml_filename
        print(f"Converting to MusicXML: {xml_path}")
        
        xml_result = transcription_service.convert_midi_to_musicxml(midi_path, xml_path)
        if not xml_result:
            raise HTTPException(status_code=500, detail="Failed to convert MIDI to MusicXML")

        # 4. Read content
        with open(xml_path, "r", encoding="utf-8") as f:
            musicxml_content = f.read()

        # Cleanup (optional - maybe keep for debugging for now)
        # try:
        #     os.remove(audio_path)
        #     os.remove(midi_path)
        #     os.remove(xml_path)
        # except:
        #     pass

        return {"musicxml": musicxml_content}

    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
