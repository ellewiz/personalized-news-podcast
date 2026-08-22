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
_SENTENCE_END_RE = re.compile(r'[.!?][\'")\]]*\s')

# Slightly slower than Google's default (1.0) — listener feedback was that
# full-speed narration came across as rushed.
SPEAKING_RATE = 0.93


def _fit_ssml(text: str) -> str:
    """Build SSML for text, trimming (at a sentence boundary when possible)
    until it fits under Google's request-size limit — a busy news day with
    no length cap on Tier 2 scripts can otherwise produce a request Google
    flatly rejects, which used to kill the whole episode run."""
    budget = len(text.encode("utf-8"))
    while True:
        ssml = pronunciation.to_ssml(text)
        if len(ssml.encode("utf-8")) <= _MAX_SSML_BYTES or not text:
            return ssml
        budget = max(0, budget - 500)
        text = text.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
        matches = list(_SENTENCE_END_RE.finditer(text + " "))
        text = text[: matches[-1].end()].strip() if matches else text.strip()


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
