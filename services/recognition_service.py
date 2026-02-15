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
            print(f"[RECOGNITION] Starting fingerprinting for: {audio_path}")
            # Generate fingerprint and match against AcoustID database
            results = acoustid.match(self.acoustid_api_key, str(audio_path))
            
            # DEBUG: Log raw results
            results_list = list(results)
            print(f"[RECOGNITION] AcoustID returned {len(results_list)} results")
            
            if not results_list:
                print(f"[RECOGNITION] WARNING: No results. API Key: {self.acoustid_api_key[:4]}...")
                return None

            # Get best match
            best_match = None
            best_score = 0
            
            print("[RECOGNITION] Candidates:")
            for score, recording_id, title, artist in results_list:
                print(f" - {title} by {artist} (Score: {score})")
                if score > best_score:
                    best_score = score
                    best_match = {
                        'score': score,
                        'recording_id': recording_id,
                        'title': title,
                        'artist': artist
                    }
            
            # Ultra-low threshold (5%) for maximum recognition recall
            if best_match and best_score > 0.05:
                print(f"[RECOGNITION] Accepted (low threshold): {best_match['title']} (Score: {best_score})")
                return best_match
            
            print(f"[RECOGNITION] Rejected best match (Score {best_score} < 0.05)")
            return None
            
        except Exception as e:
            print(f"[RECOGNITION] Error identifying song: {e}")
            return None