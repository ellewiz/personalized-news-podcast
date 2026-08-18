import base64
import subprocess
from pathlib import Path

import requests
from mutagen.mp3 import MP3

from . import config
from .models import ScriptSegment

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def synthesize_segment(segment: ScriptSegment, out_path: Path) -> Path:
    if not config.GOOGLE_TTS_API_KEY:
        raise RuntimeError("GOOGLE_TTS_API_KEY is not set")

    response = requests.post(
        GOOGLE_TTS_URL,
        params={"key": config.GOOGLE_TTS_API_KEY},
        json={
            "input": {"text": segment.text},
            "voice": {
                "languageCode": segment.language_code,
                "name": segment.voice_name,
            },
            "audioConfig": {"audioEncoding": "MP3"},
        },
        timeout=120,
    )
    response.raise_for_status()
    audio_content_b64 = response.json()["audioContent"]
    out_path.write_bytes(base64.b64decode(audio_content_b64))
    return out_path


def concatenate_mp3s(segment_paths: list[Path], out_path: Path) -> Path:
    """Concatenate segment MP3s into a single episode file. Requires ffmpeg."""
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_paths))

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    list_file.unlink(missing_ok=True)
    return out_path


def get_duration_seconds(path: Path) -> int:
    return int(MP3(path).info.length)
