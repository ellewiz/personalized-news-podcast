import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, dedupe, fetch, rss_feed, script, state as state_module, tts, weather, web_player
from .models import ScriptSegment

# The actual listening context (Skillman, NJ) — used to ground scripts in real
# broadcast time so they don't parrot a source article's own time-of-day framing.
BROADCAST_TZ = ZoneInfo("America/New_York")

CATEGORY_LABELS = {
    "nj_politics": "New Jersey Politics",
    "markets": "Markets",
    "soccer_world_cup": "Soccer and the World Cup",
    "tech_ai": "Tech and AI",
    "nfl": "the NFL",
    "nwsl": "the NWSL",
    "wnba": "the WNBA",
}

# Human-readable transcript headers for the non-category segments too.
SEGMENT_LABELS = {"tier1": "Top Headlines", "weather": "Weather", **CATEGORY_LABELS}

# Segment order: NJ politics right after Tier 1, then markets, then tech/AI,
# then all sports grouped together.
CATEGORY_ORDER = ["nj_politics", "markets", "tech_ai", "soccer_world_cup", "nfl", "nwsl", "wnba"]

# Optional per-category listener preferences, folded into the script prompt.
CATEGORY_PREFERENCES = {
    "nj_politics": (
        "Cover New Jersey state and local political news — the governor's office, the "
        "state legislature, statewide elections, and major state policy fights. Skip "
        "purely municipal-level minutiae (local zoning board disputes, town council "
        "trivia) unless it's a genuinely significant story. This listener lives in "
        "Skillman, in Montgomery Township, Somerset County — stories touching Somerset "
        "County or Central Jersey specifically are of extra interest, but statewide news "
        "matters too."
    ),
    "markets": (
        "Cover ONLY the 2 biggest stories, 3 at most — do not try to cover everything "
        "even if there's a lot of market news. Pick the single most significant items "
        "and skip the rest entirely, no matter how much is in the list below. This "
        "airs before the US market opens — be explicit about which session/market each "
        "item refers to (e.g. an Asian market's session ended hours ago and is not "
        "concurrent with a US session that hasn't started yet); never imply everything "
        "is happening 'today' in the same sense. Always state the currency or unit for "
        "every number explicitly (e.g. '16 rand per dollar,' not '16 per dollar') — "
        "never leave a bare number without its unit. If there's a major acquisition, "
        "merger, or leveraged buyout (LBO) announced, cover it even if it would "
        "otherwise be bumped for space — name who's involved (acquirer and target), "
        "the deal size if reported, and the anticipated close date or timeline if "
        "mentioned in the source material. At the 6am ET broadcast time: Asian markets "
        "(Tokyo, Hong Kong, Shanghai) have already closed for the day; European markets "
        "(London, Frankfurt, Paris) are open and mid-session; the US market hasn't opened "
        "yet. Never describe European markets as 'already wrapped' or 'closed' at "
        "broadcast time — only Asia has actually closed by then. Use these facts to keep "
        "specific claims accurate (e.g. 'which sent shares higher after Wednesday's "
        "close') — do NOT turn them into a standalone reminder sentence to the listener. "
        "Never write a sentence starting 'Remember,' 'Keep in mind,' or 'As a reminder' "
        "about market timing, and never state the same timing caveat more than once in "
        "this segment. If a company's news or earnings release outside trading hours "
        "(after close or before open), say the reaction is showing up in after-hours, "
        "pre-market, or futures trading — don't imply it happened in a session that had "
        "already ended before the news broke."
    ),
    "nfl": (
        "Prioritize major headlines and storylines about the Philadelphia Eagles "
        "specifically. Skip betting lines, odds, or prop bets entirely — not of interest."
    ),
    "soccer_world_cup": (
        "Prioritize stories specifically about the US Men's National Team (USMNT) and "
        "men's Olympic soccer. Only mention general club football (Premier League "
        "transfers, etc.) if there's genuinely nothing USMNT- or Olympics-related to "
        "cover that day, and keep any such mention brief — this listener doesn't follow "
        "club football closely. Exception: during an active FIFA World Cup tournament "
        "window, broaden coverage to the tournament generally, not just USMNT games. "
        "This segment is men's soccer only — do not include women's national team, "
        "NWSL, or other women's soccer content here, that's covered in the NWSL segment."
    ),
    "nwsl": (
        "Only cover actual National Women's Soccer League (NWSL) games, players, and "
        "league news in this segment. If the items below are about a different sport "
        "entirely (tennis, WNBA, etc.), skip those items completely — don't mention them "
        "here. The WNBA already has its own dedicated segment, so anything WNBA-specific "
        "belongs there, not here."
    ),
}

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

    missing_voices = [c for c in CATEGORY_ORDER if c not in voices.get("tier2", {})]
    if missing_voices:
        raise RuntimeError(
            f"config/voices.yaml is missing tier2 entries for: {', '.join(missing_voices)} "
            "— add a voice_name/language_code for each before running. Failing fast here "
            "instead of partway through the run, after API costs are already spent."
        )

    app_state = state_module.load_state()
    seen_guids = set(app_state["seen_guids"])

    episode_date = datetime.now(timezone.utc)
    now_local = episode_date.astimezone(BROADCAST_TZ)
    broadcast_time = now_local.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
    greeting_line = (
        f"Good morning, it's {now_local.strftime('%-I:%M %p')}, "
        f"{now_local.strftime('%A, %B %-d')}. Here is the news you can use."
    )

    cutoff = fetch.compute_cutoff(now_local)
    _log("Fetching feeds...")
    fetched = fetch.fetch_all(feeds, seen_guids, cutoff)
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
    try:
        segments: list[ScriptSegment] = [
            script.build_tier1_segment(
                tier1_items, tier1_voice["voice_name"], tier1_voice["language_code"], broadcast_time
            )
        ]
    except Exception as exc:
        # One segment's API hiccup shouldn't take down the whole episode — same
        # philosophy as the weather try/except below, applied everywhere else too.
        _log(f"  tier1 script generation failed ({exc}) — using a placeholder")
        segments = [
            ScriptSegment(
                segment_key="tier1",
                voice_name=tier1_voice["voice_name"],
                language_code=tier1_voice["language_code"],
                text="Headlines are unavailable for this segment today.",
            )
        ]

    # The greeting is code-generated (not LLM-written) so the time/date are always
    # accurate, and prepended after either the success or placeholder path above so
    # the show always opens properly regardless of how tier1 generation went.
    segments[0].text = f"{greeting_line}\n\n{segments[0].text}"

    for category in CATEGORY_ORDER:
        items = tier2_items.get(category, [])
        _log(f"  {category}...")
        category_voice = voices["tier2"][category]
        try:
            segment = script.build_tier2_segment(
                category,
                CATEGORY_LABELS.get(category, category),
                items,
                category_voice["voice_name"],
                category_voice["language_code"],
                broadcast_time,
                preferences=CATEGORY_PREFERENCES.get(category, ""),
            )
        except Exception as exc:
            _log(f"  {category} script generation failed ({exc}) — using a placeholder")
            segment = ScriptSegment(
                segment_key=category,
                voice_name=category_voice["voice_name"],
                language_code=category_voice["language_code"],
                text=f"Coverage for {CATEGORY_LABELS.get(category, category)} is unavailable today.",
            )
        segments.append(segment)
    _log("Scripts done.")

    _log("Fetching weather forecast (National Weather Service, no API key)...")
    try:
        forecast = weather.fetch_forecast(config.WEATHER_LAT, config.WEATHER_LON)
        weather_voice = voices["weather"]
        segments.append(
            script.build_weather_segment(
                forecast,
                config.WEATHER_LOCATION_LABEL,
                weather_voice["voice_name"],
                weather_voice["language_code"],
            )
        )
    except Exception as exc:
        # Weather is a nice-to-have closer, not worth failing the whole episode over.
        _log(f"  weather segment skipped ({exc})")

    # Use the NY-local calendar day, not the UTC one, so the episode's date label
    # always matches the actual broadcast day it aired on.
    episode_id = now_local.strftime("%Y-%m-%d")
    work_dir = config.EPISODES_DIR / f".tmp-{episode_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Save the full script text so a listener-reported issue (mispronunciation,
    # confusing phrasing, factual mix-up) can actually be traced back to what was
    # generated, instead of being unrecoverable once the audio's already made.
    config.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = config.EPISODES_DIR / f"{episode_id}-script.md"
    transcript_lines = [
        f"# Daily Briefing — {episode_id}",
        "",
        f"**Broadcast time:** {broadcast_time}",
        "",
    ]
    for s in segments:
        # Escape literal "$" for display only — some Markdown viewers treat a pair of
        # "$...$" as inline math and mangle everything between them. The prompt rule
        # to spell out currency in words should prevent this in practice; this is
        # just a defensive backstop for the transcript file, not the audio text.
        display_text = s.text.replace("$", r"\$")
        transcript_lines += [f"## {SEGMENT_LABELS.get(s.segment_key, s.segment_key)}", "", display_text, ""]
    transcript_path.write_text("\n".join(transcript_lines).rstrip() + "\n")

    _log("Synthesizing audio (calls the Google TTS API, one per segment)...")
    segment_paths = []
    for i, segment in enumerate(segments):
        _log(f"  {segment.segment_key}...")
        segment_path = work_dir / f"{i:02d}-{segment.segment_key}.mp3"
        try:
            tts.synthesize_segment(segment, segment_path)
        except Exception as exc:
            # A TTS hiccup on one segment drops just that segment from this
            # episode instead of losing the whole run, same reasoning as above.
            _log(f"  {segment.segment_key} audio synthesis failed ({exc}) — skipping this segment")
            continue
        segment_paths.append(segment_path)

        if i < len(segments) - 1:
            try:
                pause_path = work_dir / f"{i:02d}-pause.mp3"
                tts.synthesize_pause(PAUSE_MS, segment.voice_name, segment.language_code, pause_path)
                segment_paths.append(pause_path)
            except Exception as exc:
                _log(f"  pause after {segment.segment_key} failed ({exc}) — skipping pause")

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
        "title": f"Daily Briefing — {episode_id}",
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
