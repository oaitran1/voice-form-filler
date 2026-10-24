"""Proof check: every answer must come from the user's own words.

  ok          – supported by a quote that really is in the recording
  check       – a written section contains words/numbers the speaker never said → user must look
  unsupported – no real quote, a number not in the quote, or not a valid option → answer is blanked
"""

import re
from dataclasses import dataclass

from vff.formats import STATES
from vff.templates import MULTI_SEPARATOR, Field

QUOTE_MATCH = 0.9  # share of quote words that must appear in the recording
SHORT_WORD_MATCH = 0.5  # share of a short answer's words that must appear in its quote
TEXT_NEW_WORDS_LIMIT = 0.4  # written section: above this share of unsaid words → "check"
STATE_NAMES = {code: name for name, code in STATES.items()}  # "SC" was said as "South Carolina"
INITIAL = re.compile(r"[A-Za-z]\.?")  # a middle initial is one letter: "R" or "R."

STOPWORDS = frozenset(
    "a an the and or but of to in on at for with by from as is was were be been being he she they it his her "
    "their its this that these those i we you my our your me us him them there here then than so because "
    "about into onto over under after before during while not no yes do did does had has have".split()
)
DIGIT_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
               "six": "6", "seven": "7", "eight": "8", "nine": "9"}
NUMBER_WORDS = {**{k: int(v) for k, v in DIGIT_WORDS.items() if k != "oh"}, "ten": 10, "eleven": 11,
                "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45}


def split_multi(value: str) -> list[str]:
    """A "pick any" answer, written "Rainy; Fog" (models sometimes use commas)."""
    return [v.strip() for v in re.split(r"[;,]", value or "") if v.strip()]


@dataclass(frozen=True)
class Check:
    level: str  # "ok" | "check" | "unsupported"
    note: str = ""


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_words(text: str, min_len: int = 2) -> list[str]:
    return [w for w in _tokens(text) if w.isalpha() and len(w) >= min_len and w not in STOPWORDS]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def quote_in_transcript(quote: str, transcript: str) -> bool:
    """Is the quote really something the speaker said? (tolerates punctuation/case differences)"""
    quote_words, said_words = _tokens(quote), _tokens(transcript)
    if not quote_words:
        return False
    if " ".join(quote_words) in " ".join(said_words):
        return True
    said = set(said_words)
    return sum(w in said for w in quote_words) / len(quote_words) >= QUOTE_MATCH


def _spoken_numbers(text: str) -> tuple[set[int], str]:
    """Numbers in `text` (digits or number words), plus all digits in order (for phone numbers)."""
    words = re.findall(r"[a-z]+(?:-[a-z]+)?|\d+", text.lower())
    numbers = {int(w) for w in words if w.isdigit()} | {NUMBER_WORDS[w] for w in words if w in NUMBER_WORDS}
    digit_string = "".join(w if w.isdigit() else DIGIT_WORDS.get(w, "") for w in words)
    return numbers, digit_string


def numbers_supported(value: str, quote: str) -> bool:
    """Every number in the answer must have been said in the quote."""
    said_numbers, said_digits = _spoken_numbers(quote)
    for group in re.findall(r"\d+", value):
        if int(group) == 0:
            continue  # "7:00" — the zeros are formatting, not a claim
        if int(group) not in said_numbers and group.lstrip("0") not in said_digits:
            return False
    return True


def _short_words_supported(value: str, quote: str) -> bool:
    words = _content_words(value)
    if not words:
        return True
    quote_words = set(_tokens(quote))
    squashed = "".join(_tokens(quote))  # "j carter at yahoo" → matches "jcarter"
    return sum(w in quote_words or w in squashed for w in words) / len(words) >= SHORT_WORD_MATCH


def _new_word_share(value: str, transcript: str) -> float:
    words = _content_words(value, min_len=4)
    if not words:
        return 0.0
    said = {_stem(w) for w in _tokens(transcript)}
    return sum(_stem(w) not in said for w in words) / len(words)


def _people_named(template, draft: dict[str, dict[str, str]]) -> list[str]:
    """Names given anywhere in the form (fields whose key mentions 'name' or 'completed_by')."""
    keys = [f.key for f in template.fields if "name" in f.key or f.key == "completed_by"]
    return [draft.get(k, {}).get("value", "") for k in keys if draft.get(k, {}).get("value")]


def _names_check(value: str, names: list[str]) -> Check:
    words = set(_tokens(value))
    for name in names:
        name_parts = [w for w in _tokens(name) if w not in STOPWORDS and len(w) > 2 and w != "dr"]
        if any(part in words for part in name_parts):
            return Check("check", f"includes a name ({name}); this box must not contain names")
    return Check("ok")


def check_answers(template, draft: dict[str, dict[str, str]], transcript: str) -> dict[str, dict]:
    """Proof-check every answer. Unsupported answers are blanked; the note says what the AI had suggested."""
    results = {}
    for field in template.fields:
        value = draft.get(field.key, {}).get("value", "")
        quote = draft.get(field.key, {}).get("quote", "")
        result = check_field(field, value, quote, transcript)
        if result.level == "ok" and field.no_names:
            result = _names_check(value, _people_named(template, draft))
        note = result.note
        if result.level == "ok" and field.kind == "multi" and value:
            value = f"{MULTI_SEPARATOR} ".join(split_multi(value))
        if result.level == "unsupported":
            note, value = f"AI suggested {value!r}, removed: {result.note}", ""
        results[field.key] = {
            "label": field.label,
            "kind": field.kind,
            "value": value,
            "quote": quote if value else "",
            "check": result.level,
            "note": note,
        }
    return results


def check_field(field: Field, value: str, quote: str, transcript: str) -> Check:
    """Grade one answer against the recording."""
    value, quote = (value or "").strip(), (quote or "").strip()
    if not value:
        return Check("ok")
    if field.kind == "choice" and value not in field.options:
        return Check("unsupported", f"'{value}' is not one of {list(field.options)}")
    if field.kind == "multi":
        picked = split_multi(value)
        unknown = [v for v in picked if v not in field.options]
        if unknown:
            return Check("unsupported", f"{unknown} not in {list(field.options)}")
    if not quote:
        return Check("unsupported", "no quote from the recording")
    if not quote_in_transcript(quote, transcript):
        return Check("unsupported", "the quote is not in the recording")
    if field.format == "initial" and not INITIAL.fullmatch(value):
        return Check("unsupported", "a middle initial is one letter")
    if field.kind in ("short", "date", "time"):
        if not numbers_supported(value, quote):
            return Check("unsupported", "contains a number that was not said")
        spoken = STATE_NAMES.get(value.upper().replace(".", ""), value) if field.format == "state" else value
        if field.kind == "short" and not _short_words_supported(spoken, quote):
            return Check("unsupported", "words not found in what was said")
    if field.kind == "text":
        if not numbers_supported(value, transcript):
            return Check("check", "contains a number that was not said")
        if _new_word_share(value, transcript) > TEXT_NEW_WORDS_LIMIT:
            return Check("check", "contains details that were not said")
    return Check("ok")
