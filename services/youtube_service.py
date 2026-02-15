import os
from pathlib import Path
from typing import Optional
import yt_dlp

class YoutubeService:
    def __init__(self, download_dir: str = "temp"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)

    def download_audio(self, youtube_url: str) -> Optional[Path]:
        """
        Download audio from YouTube video as MP3.
        Returns the path to the downloaded file.
        """
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                file_path = self.download_dir / f"{info['id']}.mp3"
                return file_path
        except Exception as e:
            print(f"Error downloading YouTube audio: {e}")
            return None
