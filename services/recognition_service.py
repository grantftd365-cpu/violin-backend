import requests
import hashlib
import hmac
import base64
import time
import subprocess
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
            self.access_secret.encode('ascii'), 
            string_to_sign.encode('ascii'), 
            digestmod=hashlib.sha1
        ).digest()
        
        signature = base64.b64encode(sign).decode('ascii')
        return signature

    def _trim_audio(self, audio_path: Path, duration: int = 15) -> Optional[Path]:
        """
        Trim audio file to first N seconds using ffmpeg.
        Returns path to trimmed file, or None if failed.
        """
        try:
            temp_path = audio_path.parent / f"{audio_path.stem}_trimmed.wav"
            
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite
                '-i', str(audio_path),
                '-t', str(duration),  # First 15 seconds
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '8000',  # 8kHz (sufficient for fingerprinting and very small)
                '-ac', '1',  # Mono
                str(temp_path)
            ]
            
            print(f"[TRIM] Trimming to {duration}s: {audio_path} -> {temp_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[TRIM] ffmpeg error: {result.stderr}")
                return None
            
            if temp_path.exists():
                print(f"[TRIM] Success: {temp_path.stat().st_size} bytes")
                return temp_path
            
            return None
            
        except Exception as e:
            print(f"[TRIM] Error trimming audio: {e}")
            return None

    def identify_song(self, audio_path: Path) -> Optional[Dict[str, Any]]:
        """
        Identify song using ACRCloud API.
        Returns metadata if recognized, None otherwise.
        """
        if not self.access_key or not self.access_secret:
            print("[ACR] ERROR: Missing ACRCLOUD_ACCESS_KEY or ACRCLOUD_ACCESS_SECRET")
            return None

        trimmed_path = None
        try:
            # Step 1: Trim audio to 15 seconds to avoid size limits
            trimmed_path = self._trim_audio(audio_path, duration=15)
            
            if not trimmed_path:
                print("[ACR] Failed to trim audio, trying with full file...")
                file_to_identify = audio_path
            else:
                file_to_identify = trimmed_path

            print(f"[ACR] Identifying: {file_to_identify.name}")
            
            timestamp = str(int(time.time()))
            signature = self._generate_signature(timestamp)
            
            # Prepare multipart form
            files = {
                'sample': open(file_to_identify, 'rb')
            }
            
            data = {
                'access_key': self.access_key,
                'sample_bytes': str(os.path.getsize(file_to_identify)),
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
            # Cleanup trimmed file
            if trimmed_path and trimmed_path.exists():
                try:
                    os.remove(trimmed_path)
                except:
                    pass
            
            if 'files' in locals():
                files['sample'].close()