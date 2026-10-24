"""Pick the dropdown option that fits a fact: "right ankle" → "55 Ankle", "SC" → "SC". Never a wild guess."""

import re

MATCH_THRESHOLD = 0.5
IGNORED = frozenset("left right both my his her the a an of and or on in at to with".split())


def _words(text: str) -> set[str]:
    text = re.sub(r"\(s\)", "", text.lower())
    text = re.sub(r"^\s*\d+\s+", "", text)  # leading code: "55 Ankle" → "ankle"
    words = re.findall(r"[a-z]+", text)
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in IGNORED}


def match_option(value: str, options: tuple[str, ...]) -> tuple[str, float]:
    """(best option, score 0–1); ("", 0) when nothing fits well enough."""
    said = value.strip().lower()
    if not said:
        return "", 0.0
    for option in options:
        if option.strip().lower() == said or (said.isdigit() and option.strip().startswith(said + " ")):
            return option, 1.0
    said_words = _words(value)
    best, best_score = "", 0.0
    for option in options:
        option_words = _words(option)
        if not option_words or not said_words:
            continue
        shared = option_words & said_words
        if shared == option_words:  # every word of the option was said
            score = 0.6 + 0.1 * min(len(option_words), 4)
        else:
            score = len(shared) / len(option_words | said_words)
        if score > best_score:
            best, best_score = option, score
    return (best, best_score) if best_score >= MATCH_THRESHOLD else ("", 0.0)
