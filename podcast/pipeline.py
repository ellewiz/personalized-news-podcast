import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config, dedupe, fetch, rss_feed, script, state as state_module, tts, web_player
from .models import ScriptSegment

CATEGORY_LABELS = {
    "soccer_world_cup": "Soccer and the World Cup",
    "tech_ai": "Tech and AI",
    "nfl": "the NFL",
    "nwsl": "the NWSL",
    "wnba": "the WNBA",
}

# Segment order: tech/AI right after Tier 1, then all sports grouped together.
CATEGORY_ORDER = ["tech_ai", "soccer_world_cup", "nfl", "nwsl", "wnba"]

PAUSE_MS = 900


def _log(message: str) -> None:
    print(message, flush=True)


def run() -> Path:
    if not config.PODCAST_BASE_URL:
        raise RuntimeError(
            "PODCAST_BASE_URL is not set (e.g. https://<user>.github.io/personalized-news-podcast)"
        )

    feeds = config.load_feeds()
    voices = config.load_voices()
    app_state = state_module.load_state()
    seen_guids = set(app_state["seen_guids"])

    _log("Fetching feeds...")
    fetched = fetch.fetch_all(feeds, seen_guids)
    for key, items in fetched.items():
        _log(f"  {key}: {len(items)} new item(s)")

    tier1_items = dedupe.dedupe_items(fetched.get("tier1", []))
    tier2_items = {
        category: dedupe.dedupe_items(items)
        for category, items in fetched.items()
        if category != "tier1"
    }
    _log("Deduped.")

    _log("Generating scripts (calls the Anthropic API, one per segment)...")
    tier1_voice = voices["tier1"]
    _log("  tier1...")
    segments: list[ScriptSegment] = [
        script.build_tier1_segment(
            tier1_items, tier1_voice["voice_name"], tier1_voice["language_code"]
        )
    ]
    for category in CATEGORY_ORDER:
        items = tier2_items.get(category, [])
        _log(f"  {category}...")
        category_voice = voices["tier2"][category]
        segments.append(
            script.build_tier2_segment(
                category,
                CATEGORY_LABELS.get(category, category),
                items,
                category_voice["voice_name"],
                category_voice["language_code"],
            )
        )
    _log("Scripts done.")

    episode_date = datetime.now(timezone.utc)
    episode_id = episode_date.strftime("%Y-%m-%d")
    work_dir = config.EPISODES_DIR / f".tmp-{episode_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    _log("Synthesizing audio (calls the Google TTS API, one per segment)...")
    segment_paths = []
    for i, segment in enumerate(segments):
        _log(f"  {segment.segment_key}...")
        segment_path = work_dir / f"{i:02d}-{segment.segment_key}.mp3"
        tts.synthesize_segment(segment, segment_path)
        segment_paths.append(segment_path)

        if i < len(segments) - 1:
            pause_path = work_dir / f"{i:02d}-pause.mp3"
            tts.synthesize_pause(PAUSE_MS, segment.voice_name, segment.language_code, pause_path)
            segment_paths.append(pause_path)

    _log("Stitching segments into one episode file...")
    config.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    episode_filename = f"{episode_id}.mp3"
    episode_path = config.EPISODES_DIR / episode_filename
    # Segment files (and work_dir) are only cleaned up after a successful
    # concatenation, so a failed run leaves them behind for debugging.
    tts.concatenate_mp3s(segment_paths, episode_path)

    for p in segment_paths:
        p.unlink(missing_ok=True)
    work_dir.rmdir()

    file_size = episode_path.stat().st_size
    duration_seconds = tts.get_duration_seconds(episode_path)
    _log(f"Episode audio ready: {episode_path} ({duration_seconds}s, {file_size} bytes)")

    episode = {
        "guid": str(uuid.uuid4()),
        "title": f"Daily Briefing — {episode_date.strftime('%Y-%m-%d')}",
        "description": "Your personalized news and sports briefing.",
        "pub_date": episode_date.isoformat(),
        "audio_url": f"{config.PODCAST_BASE_URL}/episodes/{episode_filename}",
        "file_size": file_size,
        "duration_seconds": duration_seconds,
    }
    # A rerun on the same calendar day overwrites the same audio file — replace
    # that day's stale entry instead of appending a duplicate pointing at it.
    app_state["episodes"] = [
        e for e in app_state["episodes"] if e["audio_url"] != episode["audio_url"]
    ]
    app_state["episodes"].append(episode)

    all_seen_guids = {item.guid for items in fetched.values() for item in items}
    app_state["seen_guids"] = sorted(seen_guids | all_seen_guids)

    _log("Updating feed.xml, web player, and state.json...")
    rss_feed.write_feed(app_state["episodes"])
    web_player.write_index_html(app_state["episodes"])
    state_module.save_state(app_state)

    return episode_path
