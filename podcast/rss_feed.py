from dateutil import parser as dateparser
from feedgen.feed import FeedGenerator

from . import config

PODCAST_TITLE = "My Daily Briefing"
PODCAST_DESCRIPTION = "A personalized daily news and sports briefing."
PODCAST_LANGUAGE = "en-us"
PODCAST_AUTHOR = "Personalized News Podcast"


def build_feed(episodes: list[dict]) -> FeedGenerator:
    """Rebuild the full RSS feed from the episode list in state (not an incremental patch)."""
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(PODCAST_TITLE)
    fg.link(href=f"{config.PODCAST_BASE_URL}/feed.xml", rel="self")
    fg.link(href=config.PODCAST_BASE_URL or "https://example.com", rel="alternate")
    fg.description(PODCAST_DESCRIPTION)
    fg.language(PODCAST_LANGUAGE)
    fg.podcast.itunes_author(PODCAST_AUTHOR)
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_category("News")

    for episode in sorted(episodes, key=lambda e: e["pub_date"], reverse=True):
        fe = fg.add_entry()
        fe.id(episode["guid"])
        fe.title(episode["title"])
        fe.description(episode["description"])
        fe.pubDate(dateparser.isoparse(episode["pub_date"]))
        fe.enclosure(episode["audio_url"], str(episode["file_size"]), "audio/mpeg")
        fe.podcast.itunes_duration(episode["duration_seconds"])

    return fg


def write_feed(episodes: list[dict]) -> None:
    fg = build_feed(episodes)
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(config.FEED_XML_PATH))
