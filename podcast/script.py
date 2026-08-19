from anthropic import Anthropic

from . import config
from .models import FeedItem, ScriptSegment

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _items_block(items: list[FeedItem]) -> str:
    return "\n".join(f"- [{item.source_name}] {item.title}: {item.summary}" for item in items)


TIER1_PROMPT = """You are writing the "brief awareness" opening segment of a daily news \
podcast. Using ONLY the headlines below, write a short spoken-word script.

Rules:
- Total runtime target: well under 1 minute (roughly 100-130 words).
- Cover the top few headlines only, in a handful of sentences total.
- If multiple items clearly describe the same story, mention it ONCE — never stack \
multiple articles about one story.
- Plain, factual, spoken-audio tone. No headings, no bullet points, no markdown — \
just the words to be read aloud.

Headlines:
{items}

Write only the script text, nothing else."""

TIER2_PROMPT = """You are writing the "{category_label}" deep-dive segment of a daily \
news podcast. Using ONLY the items below, write a spoken-word script for this segment.

Rules:
- Narrative, engaging tone, but spoken by a SINGLE narrator — this is not a dialogue \
between two hosts, so don't write it as a conversation or use multiple speaker labels.
- Depth should scale with how much actually happened: if there's a lot below, cover it \
properly; if there's very little, give it a short mention rather than padding it out.
- Collapse near-duplicate coverage of the same story into one mention.
- No headings, no bullet points, no markdown — just the words to be read aloud.
{preferences_block}
Items:
{items}

Write only the script text, nothing else."""


WEATHER_PROMPT = """You are writing the closing weather segment of a daily news podcast \
— the classic "and now, the weather" sign-off that comes last, after the sports, the way \
local TV newscasts close out. Using ONLY the forecast details below, write a short spoken \
weather report for {location_label}.

Rules:
- Brief: 2-4 sentences, roughly 30-50 words.
- Plain, factual, spoken-audio tone.
- End on a short, natural sign-off line (e.g. wishing the listener a good day or commute).
- No headings, no bullet points, no markdown — just the words to be read aloud.

Forecast for {period_name}: {short_forecast}. High of {temperature} degrees \
{temperature_unit}. {detailed_forecast}

Write only the script text, nothing else."""


def _generate(prompt: str) -> str:
    client = _get_client()
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def build_tier1_segment(items: list[FeedItem], voice_name: str, language_code: str) -> ScriptSegment:
    if not items:
        text = "No major headlines to cover today."
    else:
        text = _generate(TIER1_PROMPT.format(items=_items_block(items)))
    return ScriptSegment(
        segment_key="tier1", voice_name=voice_name, language_code=language_code, text=text
    )


def build_tier2_segment(
    category: str,
    category_label: str,
    items: list[FeedItem],
    voice_name: str,
    language_code: str,
    preferences: str = "",
) -> ScriptSegment:
    if not items:
        text = f"Quiet news window for {category_label} today — nothing significant to report."
    else:
        preferences_block = f"\nListener preferences for this segment:\n{preferences}\n" if preferences else "\n"
        prompt = TIER2_PROMPT.format(
            category_label=category_label,
            items=_items_block(items),
            preferences_block=preferences_block,
        )
        text = _generate(prompt)
    return ScriptSegment(
        segment_key=category, voice_name=voice_name, language_code=language_code, text=text
    )


def build_weather_segment(
    forecast: dict, location_label: str, voice_name: str, language_code: str
) -> ScriptSegment:
    prompt = WEATHER_PROMPT.format(location_label=location_label, **forecast)
    text = _generate(prompt)
    return ScriptSegment(
        segment_key="weather", voice_name=voice_name, language_code=language_code, text=text
    )
