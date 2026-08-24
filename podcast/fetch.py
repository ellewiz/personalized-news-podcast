import calendar
from datetime import datetime, timedelta, timezone

import feedparser

from . import config
from .models import FeedItem


def _entry_datetime(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    # feedparser normalizes this struct_time to UTC — timegm is the correct
    # conversion (mktime assumes the input is LOCAL time, which silently
    # skews every timestamp by the machine's UTC offset).
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def _entry_guid(entry) -> str:
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def compute_cutoff(now_local: datetime) -> datetime:
    """Normally a flat RECENCY_WINDOW_HOURS lookback. On Monday, extend back to
    late Friday night instead — Friday/Saturday/Sunday news would otherwise fall
    outside a same-day window and never get covered, since no episode runs over
    the weekend. `seen_guids` still guards against re-covering anything already
    aired, so widening the window here is safe."""
    if now_local.weekday() == 0:  # Monday
        friday = now_local - timedelta(days=3)
        cutoff_local = friday.replace(hour=21, minute=0, second=0, microsecond=0)
    else:
        cutoff_local = now_local - timedelta(hours=config.RECENCY_WINDOW_HOURS)
    return cutoff_local.astimezone(timezone.utc)


def fetch_source(source: dict, segment_key: str, cutoff: datetime) -> list[FeedItem]:
    name = source.get("name", source.get("url", "unknown source"))
    try:
        parsed = feedparser.parse(source["url"])
        items = []
        for entry in parsed.entries:
            published = _entry_datetime(entry)
            if published is None or published < cutoff:
                continue
            items.append(
                FeedItem(
                    guid=_entry_guid(entry),
                    title=entry.get("title", "").strip(),
                    summary=entry.get("summary", "").strip(),
                    link=entry.get("link", ""),
                    published=published,
                    source_name=source["name"],
                    segment_key=segment_key,
                )
            )
        return items
    except Exception as exc:
        # One bad feed (down, malformed, misconfigured) shouldn't take out
        # every other source — skip it and keep going.
        print(f"  [fetch warning] {name}: {exc}", flush=True)
        return []


def fetch_all(feeds: dict, seen_guids: set[str], cutoff: datetime) -> dict[str, list[FeedItem]]:
    """Pull items newer than the recency window, excluding anything already seen."""
    results: dict[str, list[FeedItem]] = {"tier1": []}

    for source in feeds.get("tier1_general_news", []):
        results["tier1"].extend(fetch_source(source, "tier1", cutoff))

    for category, sources in feeds.get("tier2", {}).items():
        results[category] = []
        for source in sources:
            results[category].extend(fetch_source(source, category, cutoff))

    for key, items in results.items():
        fresh = [item for item in items if item.guid not in seen_guids]
        fresh.sort(key=lambda item: item.published, reverse=True)
        results[key] = fresh

    return results
