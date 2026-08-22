from html import escape

from dateutil import parser as dateparser

from . import config

PAGE_TITLE = "My Daily Briefing"
MAX_LISTED_EPISODES = 14


def _format_date(pub_date_iso: str) -> str:
    return dateparser.isoparse(pub_date_iso).strftime("%A, %B %-d")


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def render_html(episodes: list[dict]) -> str:
    ordered = sorted(episodes, key=lambda e: e["pub_date"], reverse=True)
    latest = ordered[0] if ordered else None
    older = ordered[1:MAX_LISTED_EPISODES]

    if latest is None:
        body = "<p>No episodes published yet — check back soon.</p>"
    else:
        older_items = "\n".join(
            f'''      <li>
        <div class="ep-date">{escape(_format_date(ep["pub_date"]))}</div>
        <audio controls preload="none" src="{escape(ep["audio_url"])}"></audio>
      </li>'''
            for ep in older
        )
        older_section = (
            f'\n    <h2>Previous episodes</h2>\n    <ul class="older">\n{older_items}\n    </ul>'
            if older_items
            else ""
        )
        body = f'''<h2 class="latest-date">{escape(_format_date(latest["pub_date"]))}</h2>
    <audio controls preload="metadata" src="{escape(latest["audio_url"])}"></audio>
    <p class="duration">{_format_duration(latest["duration_seconds"])}</p>{older_section}'''

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(PAGE_TITLE)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 640px;
    margin: 0 auto;
    padding: 32px 20px 64px;
    background: #fafafa;
    color: #1a1a1a;
  }}
  .artwork {{ width: 120px; height: 120px; border-radius: 16px; display: block; margin-bottom: 16px; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-top: 0; margin-bottom: 32px; }}
  h2 {{ font-size: 18px; margin-top: 40px; }}
  .latest-date {{ font-size: 22px; margin-top: 0; }}
  audio {{ width: 100%; height: 54px; }}
  .duration {{ color: #666; font-size: 14px; }}
  ul.older {{ list-style: none; padding: 0; }}
  ul.older li {{ margin-bottom: 20px; }}
  .ep-date {{ font-size: 15px; margin-bottom: 6px; color: #333; }}
</style>
</head>
<body>
  <img class="artwork" src="artwork.png" alt="{escape(PAGE_TITLE)} artwork">
  <h1>{escape(PAGE_TITLE)}</h1>
  <p class="subtitle">Your daily news &amp; sports briefing</p>
  {body}
</body>
</html>
'''


def write_index_html(episodes: list[dict]) -> None:
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (config.DOCS_DIR / "index.html").write_text(render_html(episodes))
