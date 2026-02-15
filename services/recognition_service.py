import acoustid
import musicbrainzngs
from pathlib import Path
from typing import Optional, Dict, Any
import os

class RecognitionService:
    def __init__(self):
        # Use environment variable or default to empty (limited requests)
        self.acoustid_api_key = os.getenv('ACOUSTID_API_KEY', 'cSpUJKpD') # Public test key
        # Configure MusicBrainz
        musicbrainzngs.set_useragent(
            "ViolinSheetGenerator",
            "1.0",
            "https://github.com/grantftd365-cpu/violin-backend"
        )
    
    def identify_song(self, audio_path: Path) -> Optional[Dict[str, Any]]:
        """
        Identify song using AcoustID audio fingerprinting.
        Returns metadata if found, None otherwise.
        """
        try:
            # Generate fingerprint and match against AcoustID database
            # fpcalc must be installed (libchromaprint-tools)
            results = acoustid.match(self.acoustid_api_key, str(audio_path))
            
            # Get best match
            best_match = None
            best_score = 0
            
            for score, recording_id, title, artist in results:
                if score > best_score:
                    best_score = score
                    best_match = {
                        'score': score,
                        'recording_id': recording_id,
                        'title': title,
                        'artist': artist
                    }
            
            # 50% confidence threshold is usually enough for AcoustID
            if best_match and best_score > 0.5:
                print(f"[RECOGNITION] Identified: {best_match['title']} by {best_match['artist']} (Score: {best_score})")
                return best_match
            
            return None
            
        except Exception as e:
            print(f"[RECOGNITION] Error identifying song: {e}")
            return None