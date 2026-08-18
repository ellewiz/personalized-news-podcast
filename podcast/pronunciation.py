import re
from html import escape

# Word/phrase -> how it should sound, substituted via SSML <sub alias="...">.
# Add entries here as mispronunciations turn up in real episodes.
PRONUNCIATIONS = {
    "Kyiv": "Kee-ev",
}

_PATTERN = (
    re.compile(
        r"\b(?:" + "|".join(re.escape(word) for word in PRONUNCIATIONS) + r")\b",
        re.IGNORECASE,
    )
    if PRONUNCIATIONS
    else None
)


def to_ssml(text: str) -> str:
    """Escape text as SSML, substituting known tricky pronunciations."""
    if _PATTERN is None:
        return f"<speak>{escape(text)}</speak>"

    parts = []
    last_end = 0
    for match in _PATTERN.finditer(text):
        parts.append(escape(text[last_end : match.start()]))
        matched = match.group(0)
        alias = PRONUNCIATIONS.get(matched)
        if alias is None:
            alias = next(v for k, v in PRONUNCIATIONS.items() if k.lower() == matched.lower())
        parts.append(f'<sub alias="{escape(alias)}">{escape(matched)}</sub>')
        last_end = match.end()
    parts.append(escape(text[last_end:]))
    return f"<speak>{''.join(parts)}</speak>"
