import re
from html import escape

# Word/phrase -> how it should sound, substituted via SSML <sub alias="...">.
# Add entries here as mispronunciations turn up in real episodes.
PRONUNCIATIONS = {
    "Kyiv": "Kee-ev",
}

# Acronyms that should be spelled out letter-by-letter (SSML <say-as
# interpret-as="characters">) rather than read as a word — e.g. Google's TTS
# reads "AI" as the word "eye" instead of the two letters "A" "I".
SPELL_OUT = {"AI"}

_ALL_WORDS = set(PRONUNCIATIONS) | SPELL_OUT
_PATTERN = (
    re.compile(r"\b(?:" + "|".join(re.escape(word) for word in _ALL_WORDS) + r")\b", re.IGNORECASE)
    if _ALL_WORDS
    else None
)


def _spoken_form(matched: str) -> str:
    if matched.upper() in {w.upper() for w in SPELL_OUT}:
        return f'<say-as interpret-as="characters">{escape(matched)}</say-as>'

    alias = PRONUNCIATIONS.get(matched)
    if alias is None:
        alias = next(v for k, v in PRONUNCIATIONS.items() if k.lower() == matched.lower())
    return f'<sub alias="{escape(alias)}">{escape(matched)}</sub>'


def to_ssml(text: str) -> str:
    """Escape text as SSML, substituting known tricky pronunciations."""
    if _PATTERN is None:
        return f"<speak>{escape(text)}</speak>"

    parts = []
    last_end = 0
    for match in _PATTERN.finditer(text):
        parts.append(escape(text[last_end : match.start()]))
        parts.append(_spoken_form(match.group(0)))
        last_end = match.end()
    parts.append(escape(text[last_end:]))
    return f"<speak>{''.join(parts)}</speak>"
