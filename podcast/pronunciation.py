import re
from html import escape

# Word/phrase -> how it should sound, substituted via SSML <sub alias="...">.
# Add entries here as mispronunciations turn up in real episodes.
PRONUNCIATIONS = {
    "Kyiv": "Kee-ev",
    # Google's TTS was slurring the hyphen into one word ("riskon").
    "risk-on": "risk on",
}

# Words/phrases that should be spelled out letter-by-letter (SSML <say-as
# interpret-as="characters">) rather than read as a word — e.g. Google's TTS
# reads "AI" as the word "eye" instead of the two letters "A" "I". Maps the
# matched surface form to the (punctuation-free) characters to actually speak,
# so "A.J." spells "A" "J" instead of reading the periods aloud.
SPELL_OUT = {
    "AI": "AI",
    "A.J.": "AJ",
    "NVMe": "NVME",
}

# Pause inserted between paragraphs within one segment, so a multi-story segment
# gets audible breathing room instead of sounding like one breathless run-on.
PARAGRAPH_BREAK_MS = 750

_ALL_WORDS = set(PRONUNCIATIONS) | set(SPELL_OUT)
_PATTERN = (
    # Lookaround assertions instead of \b: \b requires a word/non-word transition
    # on each side, which fails for an entry like "A.J." followed by a space —
    # both the trailing "." and the space are non-word characters, so no \b
    # transition occurs there and the match is silently skipped.
    re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(word) for word in _ALL_WORDS) + r")(?!\w)",
        re.IGNORECASE,
    )
    if _ALL_WORDS
    else None
)


def _spoken_form(matched: str) -> str:
    spell = SPELL_OUT.get(matched)
    if spell is None and matched.upper() in {w.upper() for w in SPELL_OUT}:
        spell = next(v for k, v in SPELL_OUT.items() if k.lower() == matched.lower())
    if spell is not None:
        return f'<say-as interpret-as="characters">{escape(spell)}</say-as>'

    alias = PRONUNCIATIONS.get(matched)
    if alias is None:
        alias = next(v for k, v in PRONUNCIATIONS.items() if k.lower() == matched.lower())
    return f'<sub alias="{escape(alias)}">{escape(matched)}</sub>'


def _paragraph_fragment(text: str) -> str:
    """Escape text as an SSML fragment, substituting known tricky pronunciations."""
    if _PATTERN is None:
        return escape(text)

    parts = []
    last_end = 0
    for match in _PATTERN.finditer(text):
        parts.append(escape(text[last_end : match.start()]))
        parts.append(_spoken_form(match.group(0)))
        last_end = match.end()
    parts.append(escape(text[last_end:]))
    return "".join(parts)


def to_ssml(text: str) -> str:
    """Build SSML for text, substituting known tricky pronunciations and inserting
    an audible <break> between paragraphs (blank-line-separated stories) so a
    multi-story segment doesn't sound like one continuous run-on."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not paragraphs:
        return "<speak></speak>"
    fragments = [_paragraph_fragment(p) for p in paragraphs]
    break_tag = f'<break time="{PARAGRAPH_BREAK_MS}ms"/>'
    return f"<speak>{break_tag.join(fragments)}</speak>"
