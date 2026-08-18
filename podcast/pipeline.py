import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config, dedupe, fetch, rss_feed, script, state as state_module, tts
from .models import ScriptSegment

CATEGORY_LABELS = {
    "soccer_world_cup": "Soccer and the World Cup",
    "tech_ai": "Tech and AI",
    "nfl": "the NFL",
    "nwsl": "the NWSL",
    "wnba": "the WNBA",
}


def run() -> Path:
    if not config.PODCAST_BASE_URL:
        raise RuntimeError(
            "PODCAST_BASE_URL is not set (e.g. https://<user>.github.io/personalized-news-podcast)"
        )

    feeds = config.load_feeds()
    voices = config.load_voices()
    app_state = state_module.load_state()
    seen_guids = set(app_state["seen_guids"])

    fetched = fetch.fetch_all(feeds, seen_guids)

    tier1_items = dedupe.dedupe_items(fetched.get("tier1", []))
    tier2_items = {
        category: dedupe.dedupe_items(items)
        for category, items in fetched.items()
        if category != "tier1"
    }

    tier1_voice = voices["tier1"]
    segments: list[ScriptSegment] = [
        script.build_tier1_segment(
            tier1_items, tier1_voice["voice_name"], tier1_voice["language_code"]
        )
    ]
    for category, items in tier2_items.items():
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

    episode_date = datetime.now(timezone.utc)
    episode_id = episode_date.strftime("%Y-%m-%d")
    work_dir = config.EPISODES_DIR / f".tmp-{episode_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    segment_paths = []
    try:
        for i, segment in enumerate(segments):
            segment_path = work_dir / f"{i:02d}-{segment.segment_key}.mp3"
            tts.synthesize_segment(segment, segment_path)
            segment_paths.append(segment_path)

        config.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
        episode_filename = f"{episode_id}.mp3"
        episode_path = config.EPISODES_DIR / episode_filename
        tts.concatenate_mp3s(segment_paths, episode_path)
    finally:
        for p in segment_paths:
            p.unlink(missing_ok=True)
        work_dir.rmdir()

    file_size = episode_path.stat().st_size
    duration_seconds = tts.get_duration_seconds(episode_path)

    episode = {
        "guid": str(uuid.uuid4()),
        "title": f"Daily Briefing — {episode_date.strftime('%Y-%m-%d')}",
        "description": "Your personalized news and sports briefing.",
        "pub_date": episode_date.isoformat(),
        "audio_url": f"{config.PODCAST_BASE_URL}/episodes/{episode_filename}",
        "file_size": file_size,
        "duration_seconds": duration_seconds,
    }
    app_state["episodes"].append(episode)

    all_seen_guids = {item.guid for items in fetched.values() for item in items}
    app_state["seen_guids"] = sorted(seen_guids | all_seen_guids)

    rss_feed.write_feed(app_state["episodes"])
    state_module.save_state(app_state)

    return episode_path
