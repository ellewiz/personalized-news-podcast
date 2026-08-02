import subprocess
from pathlib import Path

import requests
from mutagen.mp3 import MP3

from . import config
from .models import ScriptSegment

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize_segment(segment: ScriptSegment, out_path: Path) -> Path:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    response = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=segment.voice_id),
        headers={
            "xi-api-key": config.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": segment.text,
            "model_id": "eleven_multilingual_v2",
        },
        timeout=120,
    )
    response.raise_for_status()
    out_path.write_bytes(response.content)
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
