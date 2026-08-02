import time
from datetime import datetime, timedelta, timezone

import feedparser

from . import config
from .models import FeedItem


def _entry_datetime(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)


def _entry_guid(entry) -> str:
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def fetch_source(source: dict, segment_key: str, cutoff: datetime) -> list[FeedItem]:
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


def fetch_all(feeds: dict, seen_guids: set[str]) -> dict[str, list[FeedItem]]:
    """Pull items newer than the recency window, excluding anything already seen."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.RECENCY_WINDOW_HOURS)
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
