import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

FEEDS_PATH = REPO_ROOT / "feeds.yaml"
VOICES_PATH = REPO_ROOT / "config" / "voices.yaml"
STATE_PATH = REPO_ROOT / "state" / "state.json"
DOCS_DIR = REPO_ROOT / "docs"
EPISODES_DIR = DOCS_DIR / "episodes"
FEED_XML_PATH = DOCS_DIR / "feed.xml"

RECENCY_WINDOW_HOURS = int(os.environ.get("RECENCY_WINDOW_HOURS", "36"))

PODCAST_BASE_URL = os.environ.get("PODCAST_BASE_URL", "").rstrip("/")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
GOOGLE_TTS_API_KEY = os.environ.get("GOOGLE_TTS_API_KEY")


def load_feeds() -> dict:
    with open(FEEDS_PATH) as f:
        return yaml.safe_load(f)


def load_voices() -> dict:
    with open(VOICES_PATH) as f:
        return yaml.safe_load(f)
