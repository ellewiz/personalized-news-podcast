import re
from html import escape

# Word/phrase -> how it should sound, substituted via SSML <sub alias="...">.
# Add entries here as mispronunciations turn up in real episodes. For NFL
# player names specifically, check Pro-Football-Reference's pronunciation
# guide first: pro-football-reference.com/friv/pronunciation-guide.htm
# (grepped directly once already — worth re-checking there before guessing
# from a search snippet, which is how the original Mailata entry below
# ended up wrong).
PRONUNCIATIONS = {
    "Kyiv": "Kee-ev",
    # Google's TTS was slurring the hyphen into one word ("riskon").
    "risk-on": "risk on",
    # Eagles WR DeVonta Smith — confirmed via the PFR pronunciation guide.
    "DeVonta": "Duh-VAWN-tay",
    # Eagles OT Jordan Mailata — confirmed via the PFR pronunciation guide.
    "Mailata": "My-LOT-uh",
    # Eagles LB Zack Baun — confirmed via the PFR pronunciation guide.
    "Baun": "BAWN",
    # Eagles LB Nakobe Dean — confirmed via the PFR pronunciation guide.
    # Keyed on the first name, not "Dean", since other unrelated Deans
    # (e.g. Jamel Dean) have a different pronunciation.
    "Nakobe": "Nuh-KOH-bee",
    # Eagles TE Dallas Goedert — confirmed via the PFR pronunciation guide.
    "Goedert": "GOD-ert",
    "UEFA": "Yoo-AY-fuh",
    # Heteronym: without an accent mark, Google's TTS guessed the noun
    # ("résumés," the job documents) instead of the verb ("re-ZOOMS," as in
    # "play resumes"). Only substituted when _is_resumes_verb_usage() below
    # confirms verb context — see that function's comment for why.
    "resumes": "ree-ZOOMS",
}

# "resumes" is only forced to the verb reading when one of these subject
# words directly precedes it — see _is_resumes_verb_usage().
_RESUME_VERB_SUBJECTS = {
    "play", "trading", "action", "production", "service", "fighting",
    "hostilities", "talks", "negotiations", "classes", "school", "work",
    "the market", "the markets", "the season", "the game", "the match",
    "the tournament", "the strike", "the trial", "the hearing",
    "the meeting", "the session", "the broadcast", "the show", "the war",
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
    # Google's TTS reads the periods in "a.m."/"p.m." as sentence-ending
    # punctuation when the hour is spelled out as a word ("eleven p.m."),
    # producing an audible pause mid-abbreviation ("p." <pause> "m."). The
    # digit-adjacent, no-period form the greeting line generates ("6:00 AM")
    # doesn't have this problem — Google's own time-format heuristic already
    # reads that correctly — so only the period-bearing form needs an entry.
    "A.M.": "AM",
    "P.M.": "PM",
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


def _is_resumes_verb_usage(text: str, match_start: int) -> bool:
    """"resumes" is a heteronym: verb ("play resumes," re-ZOOMS) vs. plural
    noun ("job resumes," same reading as accented "résumés"). Google's own
    default guess is the noun reading — that's the bug the PRONUNCIATIONS
    entry above fixes — so only override it when a subject word this
    podcast's actual beats commonly use directly precedes it. Anything not
    on that list keeps Google's own guess rather than risk forcing the verb
    reading onto a genuine "résumés" usage (e.g. a story about AI screening
    job resumes) this list doesn't happen to cover — a missed fix here just
    leaves the prior, already-tolerated failure mode, not a new one."""
    preceding = text[:match_start].rstrip().lower()
    return any(preceding.endswith(subject) for subject in _RESUME_VERB_SUBJECTS)


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
        matched = match.group(0)
        if matched.lower() == "resumes" and not _is_resumes_verb_usage(text, match.start()):
            parts.append(escape(matched))
        else:
            parts.append(_spoken_form(matched))
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
