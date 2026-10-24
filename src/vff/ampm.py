"""AM/PM boxes: ticked from words said right next to the time ("2:15 p.m.", "7 that morning").

Never guessed from the hour alone. If nothing nearby says AM or PM, the AI's own (proof-checked) answer stays.
"""

import re

from vff.grounding import NUMBER_WORDS, quote_in_transcript

NEAR_CHARS = 30  # an AM/PM word must start within this many characters of the hour
_NUMBER_WORDS = "|".join(w for w in NUMBER_WORDS if NUMBER_WORDS[w] <= 12)
_AFTER_NUMBER = rf"(?:\d|\b(?:{_NUMBER_WORDS})|o'clock)\s*"
CUES = (
    ("AM", re.compile(_AFTER_NUMBER + r"(a\.?\s?m\b\.?)", re.IGNORECASE)),  # "7 am", "seven a.m." — not "I am"
    ("PM", re.compile(_AFTER_NUMBER + r"(p\.?\s?m\b\.?)", re.IGNORECASE)),
    ("AM", re.compile(r"\b(morning)\b", re.IGNORECASE)),
    ("PM", re.compile(r"\b(afternoon|evening|tonight)\b", re.IGNORECASE)),
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _hour_positions(sentence: str, hour: int) -> list[tuple[int, int]]:
    words = [str(hour)] + [w for w, n in NUMBER_WORDS.items() if n == hour]
    pattern = re.compile(rf"\b(?:{'|'.join(map(re.escape, words))})\b", re.IGNORECASE)
    return [(m.start(), m.end()) for m in pattern.finditer(sentence)]


def _nearest_cue(sentence: str, start: int, end: int) -> tuple[str, str, int] | None:
    """(AM/PM, the words said, distance) for the closest cue to the hour at sentence[start:end]."""
    best = None
    for choice, pattern in CUES:
        for match in pattern.finditer(sentence):
            cue_start, cue_end = match.span(1)
            distance = cue_start - end if cue_start >= end else start - cue_end
            if distance <= NEAR_CHARS and (best is None or distance < best[2]):
                best = (choice, match.group(1), distance)
    return best


def find_ampm(time_value: str, time_quote: str, transcript: str) -> tuple[str, str]:
    """('AM' | 'PM' | '', the sentence that says so) for a time answer like '2:15'."""
    hour_match = re.match(r"(\d{1,2})", time_value)
    if not hour_match:
        return "", ""
    hour = int(hour_match.group(1))
    sentences = [s for s in _SENTENCE_END.split(transcript) if _hour_positions(s, hour)]
    quoted = [s for s in sentences if time_quote and quote_in_transcript(time_quote, s)]
    best = None
    for sentence in quoted or sentences:
        for start, end in _hour_positions(sentence, hour):
            cue = _nearest_cue(sentence, start, end)
            if cue and (best is None or cue[2] < best[0][2]):
                best = (cue, sentence)
    if best is None:
        return "", ""
    (choice, _, _), sentence = best
    return choice, sentence.strip()


def fill_ampm(template, answers: dict[str, dict], transcript: str) -> dict[str, dict]:
    """Return a new answers dict with every AM/PM box set from what was said next to its time."""
    result = dict(answers)
    for field in template.fields:
        if not field.time_of:
            continue
        time = answers.get(field.time_of, {})
        choice, sentence = find_ampm(time.get("value", ""), time.get("quote", ""), transcript)
        if not choice or choice not in field.options:
            continue
        previous = answers.get(field.key, {})
        overruled = previous.get("value") and previous["value"] != choice
        note = f"AI said {previous['value']!r}; the recording says {choice}" if overruled else ""
        result[field.key] = {**previous, "label": field.label, "kind": field.kind,
                             "value": choice, "quote": sentence, "check": "ok", "note": note}
    return result
