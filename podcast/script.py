import re

from anthropic import Anthropic

from . import config
from .models import FeedItem, ScriptSegment

_SENTENCE_END_RE = re.compile(r'[.!?][\'")\]]*\s')

# Rare model glitch: a stray CJK token leaking into otherwise-English output
# (e.g. "could决定 where"). Narrow to CJK ranges only — NOT a broad non-ASCII
# check, since legitimate accented Latin names (González, Čeferin) show up
# constantly and correctly.
_UNEXPECTED_SCRIPT_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")

# A period closing an abbreviation rather than a sentence. _SENTENCE_END_RE on
# its own splits "the U.S. session hasn't opened yet" into two fragments, which
# would hide a timing caveat from _is_timing_caveat() below instead of catching
# it — the caveat's opener lands in one fragment and its subject in the other.
_ABBREVIATION_TAIL_RE = re.compile(
    r"(?:^|\s)(?:"
    r"[A-Za-z]\."  # a lone initial: "J."
    r"|(?:[A-Za-z]\.){2,}"  # a dotted abbreviation: "U.S.", "a.m."
    r"|(?:Mr|Mrs|Ms|Dr|Prof|Sen|Rep|Gov|Gen|St|Jr|Sr|Inc|Corp|Co|Ltd|vs|etc|No)\."
    r")$"
)

# A sentence whose whole job is reminding the listener what time it is or which
# market is open — "Remember, the US session hasn't opened yet, so all of this is
# still setting the stage." The prompts hand the model 6am session-status facts so
# its claims stay accurate, and it keeps narrating them back as an aside instead
# (see the README's overcorrection entries). Matching needs all three parts: a
# reminder opener, a market/session subject, and a timing word — so an ordinary
# sentence that merely starts with "Remember" survives.
_CAVEAT_OPENER_RE = re.compile(
    r"^\W*(?:remember|keep in mind|bear in mind|(?:just )?a(?:s a)? reminder"
    r"|(?:it'?s )?worth remembering|note that|mind you|again)\b",
    re.IGNORECASE,
)
_SESSION_SUBJECT_RE = re.compile(
    r"\b(?:market|markets|session|sessions|trading|bell|exchange|exchanges"
    r"|futures|premarket|pre-market|wall street)\b",
    re.IGNORECASE,
)
_SESSION_TIMING_RE = re.compile(
    r"\b(?:yet|still|already|ahead|until|so far|right now|this morning|at this hour)\b"
    r"|\b(?:has|have|is|are|do|does|did|wo|ca)n['\u2019]?t\b",
    re.IGNORECASE,
)

_client: Anthropic | None = None


def _log(message: str) -> None:
    # Same print-to-stdout convention as pipeline._log(); the launchd job sends
    # stdout to logs/publish.log, so anything here lands in the run's log.
    print(message, flush=True)


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _items_block(items: list[FeedItem]) -> str:
    return "\n".join(f"- [{item.source_name}] {item.title}: {item.summary}" for item in items)


# Shared broadcast-writing rules for both news segments, based on standard radio/podcast
# script-writing practice: write for the ear (a listener gets one pass, can't rewind), so
# sentences stay short and declarative, one idea at a time, instead of the dense,
# multi-clause paragraphs that read fine on a page but sound breathless out loud.
BROADCAST_STYLE_RULES = """- Short, declarative sentences, roughly 8-20 words each. One idea or fact per sentence.
- Avoid stacking multiple independent clauses with em-dashes or semicolons — give the \
narrator room to breathe. Prefer separate sentences over one long one.
- Subject-verb-object construction. Conversational, as if speaking to one listener.
- Use signposting words between stories (first, next, meanwhile, also) so the listener \
can follow the structure by ear.
- On first mention of a person or organization the listener may not recognize, briefly \
identify them with a short appositive (e.g. "Vinod Khosla, the venture capitalist," not \
just "Vinod Khosla"). Skip this for well-known figures or companies.
- State every number's unit, currency, or comparison explicitly — never leave a bare \
number dangling (e.g. "16 rand per dollar," not "16 per dollar"; "up 3 percent," not \
just "up 3"). Always spell out currency as words ("89 million dollars"), never use the \
"$" symbol.
- This listener is American and wants money figures in US dollars. If an item gives a \
price only in a foreign currency, do not present it as the price. Use the US-dollar \
figure when the source material has one — including from a different item below covering \
the same story, which may well price it for its own market instead. When only a \
foreign-currency figure exists, either say whose country's price it is ("about two \
thousand pounds in the UK") or leave the number out entirely. Never convert a foreign \
amount into dollars yourself: you don't have today's exchange rate, and an overseas \
retail price carries different local taxes and regional pricing anyway, so a converted \
figure is not the US price. Only pair a foreign amount with a dollar figure when the \
source material itself supplies both.
- Avoid vague filler that doesn't actually convey information (e.g. don't say a company \
"continued making its mark" or mention a "broader roundup" — say specifically what \
happened).
- Avoid lazy scene-setting words that imply drama without evidence for it — especially \
"quietly" (e.g. "quietly built," "quietly rolled out"). If a source doesn't actually \
describe secrecy or a low profile, don't imply one; just say what happened.
- No meta-commentary about the show's own format, timing, or editorial choices. Don't \
tell the listener why a story is or isn't covered, or why a segment is wrapping up. She \
also knows perfectly well when she's listening, so never remind her what time it is or \
what hasn't happened yet at this hour — no "Remember, the US market hasn't opened yet," \
and no reworded version of it either. Report the news and stop.
- Skip throwaway filler phrases ("of course," "needless to say," "as you'd expect") that \
add words without adding information.
- When you say one event affects, complicates, or drives another — especially across \
different markets or countries — briefly say why or how, not just that it does. A bare \
causal claim with no mechanism leaves the listener guessing.
- Don't reference a specific detail (what a quote said, what an injury was, what a \
decision entailed) unless the source material actually tells you what it is. If the \
source only gestures at "his comments" or "the injury" without specifics, omit the \
reference or keep it general — don't imply detail you don't actually have.
- Write each distinct story or idea as its own short paragraph, separated by a blank \
line. Paragraph breaks are expected and encouraged."""

TIER1_PROMPT = """You are writing the "brief awareness" opening segment of a daily news \
podcast. This episode is being generated and published at {broadcast_time} — the listener \
will hear it shortly after that. Using ONLY the headlines below, write a short spoken-word \
script.

Rules:
- Total runtime target: well under 1 minute (roughly 100-130 words).
- Cover the top few headlines only, in a handful of sentences total.
- If multiple items clearly describe the same story, mention it ONCE — never stack \
multiple articles about one story.
- Plain, factual, spoken-audio tone. No headings, no numbered/bulleted lists, no markdown \
symbols (#, *, -) — but do use paragraph breaks between stories, per the writing-style \
rules below.
- Do NOT copy time-of-day words ("this morning", "tonight", "good evening", etc.) \
straight from a headline or summary — those were written by the source at whatever time \
THEY published, which is not the broadcast time above. If timing matters, describe it \
relative to the broadcast time (e.g. "overnight," "earlier today") instead of assuming \
the source's framing still applies.
- Do NOT write any greeting or opening salutation of your own ("good morning," "here's \
the news," etc.) — a greeting line is added separately, before your text. Start straight \
in with the first headline.

Writing style — this is spoken audio, not text read on a screen:
{style_rules}

Headlines:
{items}

Write only the script text, nothing else."""

TIER2_PROMPT = """You are writing the "{category_label}" deep-dive segment of a daily \
news podcast. This episode is being generated and published at {broadcast_time} — the \
listener will hear it shortly after that, and this segment runs mid-episode, not as a \
fresh opening. Using ONLY the items below, write a spoken-word script for this segment.

Rules:
- Narrative, engaging tone, but spoken by a SINGLE narrator — this is not a dialogue \
between two hosts, so don't write it as a conversation or use multiple speaker labels.
- Depth should scale with how much actually happened: if there's a lot below, cover it \
properly; if there's very little, give it a short mention rather than padding it out.
- Collapse near-duplicate coverage of the same story into one mention.
- No headings, no numbered/bulleted lists, no markdown symbols (#, *, -) — but do use \
paragraph breaks between stories, per the writing-style rules below.
- Do NOT copy time-of-day words ("this morning", "tonight", "good evening", etc.) \
straight from a headline or summary — those were written by the source at whatever time \
THEY published, which is not the broadcast time above. If an item concerns a different \
time zone (e.g. an overseas market or event), name that session inside the sentence \
reporting the news, rather than implying it's happening "now" relative to the broadcast \
time — e.g. "shares fell in Tokyo's session, which closed hours ago," not a bare "shares \
fell today." Never add a separate aside telling the listener what is or isn't open at \
broadcast time. Also avoid vague relative-time phrases that don't say which \
session or day they mean ("recent trading," "lately," "in recent sessions") — name the \
actual session or timeframe instead (e.g. "Wednesday's session," "overnight," \
"in after-hours trading").
- Never open with a greeting ("good morning," "good evening") — this segment continues \
mid-episode, it is not a fresh start.
- Vary how you open this segment. Don't default to a generic transition phrase like \
"Turning to X," "Let's turn to X," or "We turn now to X" — every other segment in this \
episode is written the same way you're being asked to write this one, so if everyone \
defaults to the same construction, the whole episode opens every segment identically. \
Start with something specific to today's actual content instead.
{avoid_openers_block}
Writing style — this is spoken audio, not text read on a screen:
{style_rules}
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
- Plain, factual, spoken-audio tone. Short, declarative, subject-verb-object sentences.
- State the unit for every measurement you mention (temperature, wind speed, etc.) — \
never leave a bare number.
- End on a short, natural sign-off line (e.g. wishing the listener a good day or commute).
- No headings, no bullet points, no markdown — just the words to be read aloud.

Forecast for {period_name}: {short_forecast}. High of {temperature} degrees \
{temperature_unit}. {detailed_forecast}

Write only the script text, nothing else."""


# Below this length, a trailing paragraph right at a known max_tokens cutoff reads
# as an unfinished new-topic teaser (e.g. "Bill Gates... is sounding an alarm on a
# related front." with no follow-through) rather than a deliberate short closer.
_MIN_TRAILING_PARAGRAPH_CHARS = 120


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping each one's trailing whitespace so the
    pieces rejoin exactly. Treats a period that closes an abbreviation ("U.S.,"
    "a.m.," "Sen.") as part of the sentence rather than the end of one.
    Deliberately conservative: where it can't tell, it leaves text joined, so a
    caller that drops matched sentences under-removes rather than cutting one in
    half."""
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text + " "):
        candidate = text[start : match.end()]
        if _ABBREVIATION_TAIL_RE.search(candidate.rstrip()):
            continue
        sentences.append(candidate)
        start = match.end()
    if text[start:].strip():
        sentences.append(text[start:])
    return sentences


def _is_timing_caveat(sentence: str) -> bool:
    return bool(
        _CAVEAT_OPENER_RE.match(sentence.strip())
        and _SESSION_SUBJECT_RE.search(sentence)
        and _SESSION_TIMING_RE.search(sentence)
    )


def _strip_timing_caveats(text: str) -> str:
    """Drop any sentence that exists only to remind the listener the market
    isn't open yet. Three rounds of prompt wording haven't held on their own
    (see the README), so this is the deterministic backstop.

    Drops the whole sentence rather than surgically removing the caveat clause:
    rewriting generated prose mid-sentence risks ungrammatical audio, and these
    asides rarely carry anything the surrounding paragraph hasn't already said.
    It logs every drop so the rare case where a trailing clause did carry
    something real is visible in publish.log instead of silent."""
    kept_paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        kept = []
        for sentence in _split_sentences(paragraph):
            if _is_timing_caveat(sentence):
                _log(f"    dropped a market-timing caveat: {sentence.strip()!r}")
                continue
            kept.append(sentence)
        rebuilt = "".join(kept).strip()
        if rebuilt:
            kept_paragraphs.append(rebuilt)
    return "\n\n".join(kept_paragraphs)


def _trim_to_last_sentence(text: str) -> str:
    """If a response got cut off mid-sentence, trim back to the last complete
    one rather than shipping audio that ends mid-word. Also drops a short
    trailing paragraph entirely, since a cutoff this abrupt is more likely to
    have landed on a dangling intro than a real conclusion — only called when
    stop_reason is already known to be max_tokens, so a normal, complete
    generation with a legitimately short closer never goes through this."""
    matches = list(_SENTENCE_END_RE.finditer(text + " "))
    if not matches:
        return text
    trimmed = text[: matches[-1].end()].strip()
    paragraphs = re.split(r"\n\s*\n", trimmed)
    if len(paragraphs) > 1 and len(paragraphs[-1]) < _MIN_TRAILING_PARAGRAPH_CHARS:
        trimmed = "\n\n".join(paragraphs[:-1]).strip()
    return trimmed


def first_sentence(text: str) -> str:
    """The opening sentence of a segment, used to show later segments what
    opening constructions are already taken this episode. Uses the same
    abbreviation-aware split as above, so an opener like "U.S. stocks slipped
    overnight." isn't handed forward as a useless bare "U.S." """
    sentences = _split_sentences(text)
    return sentences[0].strip() if sentences else text.strip()


def _generate(prompt: str) -> str:
    client = _get_client()
    text = ""
    # A busy news day can legitimately produce a long Tier 2 script (no length
    # cap in that prompt) — 1024 tokens was too tight and silently truncated
    # mid-word; 2048 still wasn't enough on the busiest days, raised to 3072.
    # Retry once on a genuinely empty response before giving up.
    for _attempt in range(2):
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=3072,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if response.stop_reason == "max_tokens":
            text = _trim_to_last_sentence(text)
        if text and not _UNEXPECTED_SCRIPT_RE.search(text):
            return _strip_timing_caveats(text)
    return _strip_timing_caveats(text) or "(Content unavailable for this segment.)"


def build_tier1_segment(
    items: list[FeedItem], voice_name: str, language_code: str, broadcast_time: str
) -> ScriptSegment:
    if not items:
        text = "No major headlines to cover today."
    else:
        text = _generate(
            TIER1_PROMPT.format(
                items=_items_block(items),
                broadcast_time=broadcast_time,
                style_rules=BROADCAST_STYLE_RULES,
            )
        )
    return ScriptSegment(
        segment_key="tier1", voice_name=voice_name, language_code=language_code, text=text
    )


def build_tier2_segment(
    category: str,
    category_label: str,
    items: list[FeedItem],
    voice_name: str,
    language_code: str,
    broadcast_time: str,
    preferences: str = "",
    avoid_openers: list[str] | None = None,
) -> ScriptSegment:
    if not items:
        text = f"Quiet news window for {category_label} today — nothing significant to report."
    else:
        preferences_block = f"\nListener preferences for this segment:\n{preferences}\n" if preferences else "\n"
        # Each segment is a separate, stateless API call with no visibility into what
        # the others wrote — without this, every segment tends to independently default
        # to the same generic transition phrase ("Turning to X"), since nothing else
        # nudges it toward variety. Passing forward the opening sentences already used
        # this episode gives each subsequent segment enough cross-episode awareness to
        # avoid repeating them, without a separate editing pass over the whole episode.
        if avoid_openers:
            quoted = "\n".join(f'- "{o}"' for o in avoid_openers)
            avoid_openers_block = (
                f"\nOther segments in this episode already opened with:\n{quoted}\n"
                "Don't reuse any of those constructions for this segment's opening line.\n"
            )
        else:
            avoid_openers_block = ""
        prompt = TIER2_PROMPT.format(
            category_label=category_label,
            items=_items_block(items),
            preferences_block=preferences_block,
            broadcast_time=broadcast_time,
            style_rules=BROADCAST_STYLE_RULES,
            avoid_openers_block=avoid_openers_block,
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
