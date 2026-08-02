import difflib
import re

from .models import FeedItem

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def _normalize(title: str) -> str:
    return _PUNCT_RE.sub("", title.lower()).strip()


def dedupe_items(items: list[FeedItem], similarity_threshold: float = 0.72) -> list[FeedItem]:
    """Collapse near-duplicate coverage of the same story.

    Items should already be sorted newest-first; the first (freshest) item in
    each near-duplicate cluster is kept.
    """
    kept: list[FeedItem] = []
    kept_norms: list[str] = []

    for item in items:
        norm = _normalize(item.title)
        if any(
            difflib.SequenceMatcher(None, norm, existing).ratio() >= similarity_threshold
            for existing in kept_norms
        ):
            continue
        kept.append(item)
        kept_norms.append(norm)

    return kept
