import requests
import hashlib
import hmac
import base64
import time
from pathlib import Path
from typing import Optional, Dict, Any
import os

class RecognitionService:
    def __init__(self):
        # ACRCloud Configuration
        self.host = os.getenv('ACRCLOUD_HOST', 'identify-cn-north-1.acrcloud.cn')
        self.access_key = os.getenv('ACRCLOUD_ACCESS_KEY', '')
        self.access_secret = os.getenv('ACRCLOUD_ACCESS_SECRET', '')
        self.timeout = 10 # seconds

    def _generate_signature(self, timestamp: str) -> str:
        """Generate HMAC-SHA1 signature required by ACRCloud"""
        http_method = "POST"
        http_uri = "/v1/identify"
        data_type = "audio"
        signature_version = "1"
        
        string_to_sign = f"{http_method}\n{http_uri}\n{self.access_key}\n{data_type}\n{signature_version}\n{timestamp}"
        
        sign = hmac.new(
            self.access_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        signature = base64.b64encode(sign).decode('utf-8')
        return signature

    def identify_song(self, audio_path: Path) -> Optional[Dict[str, Any]]:
        """
        Identify song using ACRCloud API.
        Returns metadata if recognized, None otherwise.
        """
        if not self.access_key or not self.access_secret:
            print("[ACR] ERROR: Missing ACRCLOUD_ACCESS_KEY or ACRCLOUD_ACCESS_SECRET")
            return None

        try:
            print(f"[ACR] Identifying: {audio_path.name}")
            
            timestamp = str(int(time.time()))
            signature = self._generate_signature(timestamp)
            
            # Prepare multipart form
            files = {
                'sample': open(audio_path, 'rb')
            }
            
            data = {
                'access_key': self.access_key,
                'sample_bytes': str(os.path.getsize(audio_path)),
                'timestamp': timestamp,
                'signature': signature,
                'data_type': 'audio',
                'signature_version': '1'
            }
            
            url = f"https://{self.host}/v1/identify"
            print(f"[ACR] Sending request to {url}")
            
            response = requests.post(url, files=files, data=data, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"[ACR] HTTP Error: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            print(f"[ACR] Response: {result}")
            
            # Parse ACRCloud response
            status = result.get('status', {})
            if status.get('code') == 0:
                # Success!
                metadata = result.get('metadata', {})
                if 'music' in metadata and len(metadata['music']) > 0:
                    music = metadata['music'][0]
                    title = music.get('title')
                    artists = [a.get('name') for a in music.get('artists', [])]
                    artist_str = ", ".join(artists)
                    score = music.get('score')
                    
                    print(f"[ACR] Match found: {title} by {artist_str} (Score: {score})")
                    
                    return {
                        "title": title,
                        "artist": artist_str,
                        "score": score,
                        "raw": music
                    }
                else:
                    print("[ACR] No music match found in metadata")
            else:
                print(f"[ACR] API Error {status.get('code')}: {status.get('msg')}")
                
            return None
            
        except Exception as e:
            print(f"[ACR] Error identifying song: {e}")
            return None
        finally:
            if 'files' in locals():
                files['sample'].close()