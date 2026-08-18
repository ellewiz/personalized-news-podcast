from dataclasses import dataclass
from datetime import datetime


@dataclass
class FeedItem:
    guid: str
    title: str
    summary: str
    link: str
    published: datetime
    source_name: str
    segment_key: str  # "tier1" or a tier2 category key (e.g. "nfl")


@dataclass
class ScriptSegment:
    segment_key: str
    voice_name: str
    language_code: str
    text: str
