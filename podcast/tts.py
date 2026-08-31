import base64
import re
from pathlib import Path

import requests
from mutagen.mp3 import MP3

from . import config, pronunciation
from .models import ScriptSegment

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Google Cloud TTS hard-rejects any request with input text/SSML over 5000
# bytes (a 400 Bad Request). Leave real margin below that for markup
# overhead pronunciation.to_ssml() adds (<speak>, <sub>, <say-as> tags).
_MAX_SSML_BYTES = 4900

# Slightly slower than Google's default (1.0) — listener feedback was that
# full-speed narration came across as rushed.
SPEAKING_RATE = 0.93


def _fit_ssml(text: str) -> str:
    """Build SSML for text, dropping whole trailing paragraphs (each one a
    distinct story, per pronunciation.to_ssml's blank-line splitting) until
    it fits under Google's request-size limit — a busy news day with no
    length cap on Tier 2 scripts can otherwise produce a request Google
    flatly rejects, which used to kill the whole episode run.

    Trims at paragraph granularity rather than an arbitrary byte offset:
    a raw byte-slice can land mid-story (or even mid-character on a
    multi-byte UTF-8 boundary), and re-snapping to the nearest earlier
    sentence after an oversized cut tends to overshoot, dropping more than
    was actually necessary to fit. Since a paragraph is already the atomic
    unit of a story here, this only ever drops as many whole stories as
    required, never a partial one.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    original_count = len(paragraphs)
    while paragraphs:
        ssml = pronunciation.to_ssml("\n\n".join(paragraphs))
        if len(ssml.encode("utf-8")) <= _MAX_SSML_BYTES:
            if len(paragraphs) < original_count:
                dropped = original_count - len(paragraphs)
                print(
                    f"  ⚠ segment trimmed to fit Google TTS's {_MAX_SSML_BYTES}-byte "
                    f"request limit — dropped {dropped} trailing paragraph(s) of "
                    f"{original_count}",
                    flush=True,
                )
            return ssml
        paragraphs.pop()
    return "<speak></speak>"


def synthesize_segment(segment: ScriptSegment, out_path: Path) -> Path:
    if not config.GOOGLE_TTS_API_KEY:
        raise RuntimeError("GOOGLE_TTS_API_KEY is not set")

    response = requests.post(
        GOOGLE_TTS_URL,
        params={"key": config.GOOGLE_TTS_API_KEY},
        json={
            "input": {"ssml": _fit_ssml(segment.text)},
            "voice": {
                "languageCode": segment.language_code,
                "name": segment.voice_name,
            },
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": SPEAKING_RATE},
        },
        timeout=120,
    )
    response.raise_for_status()
    audio_content_b64 = response.json()["audioContent"]
    out_path.write_bytes(base64.b64decode(audio_content_b64))
    return out_path


def synthesize_pause(duration_ms: int, voice_name: str, language_code: str, out_path: Path) -> Path:
    """A silent clip, generated via SSML <break>, used as a gap between segments."""
    if not config.GOOGLE_TTS_API_KEY:
        raise RuntimeError("GOOGLE_TTS_API_KEY is not set")

    response = requests.post(
        GOOGLE_TTS_URL,
        params={"key": config.GOOGLE_TTS_API_KEY},
        json={
            "input": {"ssml": f'<speak><break time="{duration_ms}ms"/></speak>'},
            "voice": {
                "languageCode": language_code,
                "name": voice_name,
            },
            "audioConfig": {"audioEncoding": "MP3"},
        },
        timeout=60,
    )
    response.raise_for_status()
    audio_content_b64 = response.json()["audioContent"]
    out_path.write_bytes(base64.b64decode(audio_content_b64))
    return out_path


def concatenate_mp3s(segment_paths: list[Path], out_path: Path) -> Path:
    """Concatenate segment MP3s into a single episode file.

    Plain binary concatenation, not ffmpeg. Google Cloud TTS returns each
    segment as a plain MP3 frame stream with no container-level metadata, so
    concatenating the raw bytes plays back correctly — and it sidesteps a
    subprocess/fork crash ffmpeg was hitting when invoked from this process
    on macOS (a known fork-safety issue with Apple's media/network
    frameworks in multi-threaded processes).
    """
    with open(out_path, "wb") as out_file:
        for segment_path in segment_paths:
            out_file.write(segment_path.read_bytes())
    return out_path


def get_duration_seconds(path: Path) -> int:
    return int(MP3(path).info.length)
