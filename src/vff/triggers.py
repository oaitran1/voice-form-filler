"""Spoken cues: "start recording" begins a recording, "stop recording" ends it.

A stop phrase only counts when it is the LAST thing said, so mentioning it mid-story
("stop recording is what I said yesterday") does not stop anything.
"""

import re

DEFAULT_START_PHRASES = ("start recording", "begin recording", "start the recording", "started recording")  # last = Whisper mishearing
DEFAULT_STOP_PHRASES = ("stop recording", "end recording", "i'm done recording", "stopped recording")  # last = Whisper mishearing

_WORD = r"[a-z']+"
_LEAD_SEPARATORS = r"[\s,;:\-]*"  # keeps the sentence's own period: "science. Stop recording." → "science."
_TRAILING_PUNCT = r"[\s.!?,]*$"


def _normalize_apostrophes(text: str) -> str:
    return text.replace("’", "'")


def _words(text: str) -> list[str]:
    return re.findall(_WORD, _normalize_apostrophes(text).lower())


def parse_stop_phrases(setting: str) -> tuple[str, ...]:
    """'Finish up, END NOW' → ('finish up', 'end now'). Empty → defaults."""
    phrases = tuple(" ".join(_words(part)) for part in setting.split(","))
    phrases = tuple(p for p in phrases if p)
    return phrases or DEFAULT_STOP_PHRASES


def ends_with_stop_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """True if `text` ends with one of the stop phrases (ignoring case and punctuation)."""
    words = _words(text)
    for phrase in phrases:
        target = phrase.split()
        if target and words[-len(target):] == target:
            return True
    return False


def after_start_phrase(text: str, phrases: tuple[str, ...] = DEFAULT_START_PHRASES) -> str | None:
    """If a start phrase was said, whatever came after it in the same breath ('' if nothing); None if not said."""
    cleaned = _normalize_apostrophes(text)
    for phrase in phrases:
        body = r"[^a-z']+".join(re.escape(w) for w in phrase.split())
        found = re.search(r"\b" + body + r"\b", cleaned, re.IGNORECASE)
        if found:
            return cleaned[found.end():].strip(" .,!?;:-")
    return None


def _phrase_at_end_pattern(phrase: str) -> re.Pattern[str]:
    body = r"[^a-z']+".join(re.escape(w) for w in phrase.split())
    return re.compile(_LEAD_SEPARATORS + r"\b" + body + _TRAILING_PUNCT, re.IGNORECASE)


def strip_stop_phrase(text: str, phrases: tuple[str, ...]) -> str:
    """Remove a trailing stop phrase so it never ends up in the saved story."""
    cleaned = _normalize_apostrophes(text)
    for phrase in phrases:
        stripped = _phrase_at_end_pattern(phrase).sub("", cleaned)
        if stripped != cleaned:
            return stripped.strip()
    return text
