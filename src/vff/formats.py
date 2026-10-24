"""Write each answer the way its box expects: dates as MM/DD/YYYY, states as 2-letter codes, ZIP digits, phones.

Runs after the proof check (the check compares the user's own words). Never invents anything: a missing year
stays missing, and anything it can't read is left exactly as said.
"""

import re
from pathlib import Path

from pypdf import PdfReader

MONTHS = {name: i for i, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
     ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
     ("dec", "december")], start=1) for name in names}
STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}
_SPOKEN_DATE = re.compile(r"^([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?$", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{4}))?$")
# Adobe's built-in format scripts → our format names
_ADOBE_FORMATS = (
    (re.compile(r"AFSpecial_Format\(\s*[01]\s*\)"), "zip"),
    (re.compile(r"AFSpecial_Format\(\s*2\s*\)"), "phone"),
    (re.compile(r"AFDate_Format(?:Ex)?\(\s*\"m+/d+/y{4}\"", re.IGNORECASE), "mm/dd/yyyy"),
)


def _date(value: str) -> str:
    text = value.strip()
    spoken, numeric = _SPOKEN_DATE.match(text), _NUMERIC_DATE.match(text)
    if spoken and spoken.group(1).lower() in MONTHS:
        month, day, year = MONTHS[spoken.group(1).lower()], int(spoken.group(2)), spoken.group(3)
    elif numeric:
        month, day, year = int(numeric.group(1)), int(numeric.group(2)), numeric.group(3)
    else:
        return value
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return value
    return f"{month:02d}/{day:02d}" + (f"/{year}" if year else "")


def _state(value: str) -> str:
    text = " ".join(value.lower().replace(".", "").split())
    if text.upper() in STATES.values():
        return text.upper()
    return STATES.get(text, value)


def _zip(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 5:
        return digits
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 9 else value


def _phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else value


FORMATTERS = {"mm/dd/yyyy": _date, "state": _state, "zip": _zip, "phone": _phone}


def format_value(fmt: str, value: str) -> str:
    """Rewrite `value` in format `fmt`; unknown format or unreadable value → unchanged."""
    formatter = FORMATTERS.get(fmt)
    return formatter(value) if formatter and value else value


def _format_script(field) -> str:
    actions = field.get("/AA") or {}
    if "/F" not in actions:
        return ""
    script = actions["/F"].get_object().get("/JS", "")
    script = script.get_object() if hasattr(script, "get_object") else script
    return script.get_data().decode("latin-1") if hasattr(script, "get_data") else str(script)


def form_formats(pdf_path: Path | None) -> dict[str, str]:
    """{box name: format} read from the form's own Adobe format scripts (e.g. its ZIP boxes)."""
    if pdf_path is None:
        return {}
    formats = {}
    for name, field in (PdfReader(pdf_path).get_fields() or {}).items():
        script = _format_script(field)
        found = next((fmt for pattern, fmt in _ADOBE_FORMATS if pattern.search(script)), None)
        if found:
            formats[name] = found
    return formats


def apply_formats(template, answers: dict[str, dict], pdf_formats: dict[str, str] | None = None) -> dict[str, dict]:
    """Return a new answers dict with values written in each box's format (template first, then the form's own)."""
    pdf_formats = form_formats(template.pdf_path) if pdf_formats is None else pdf_formats
    result = dict(answers)
    for field in template.fields:
        fmt = field.format or pdf_formats.get(field.pdf_field, "")
        entry = answers.get(field.key)
        if fmt and entry and entry.get("value"):
            result[field.key] = {**entry, "value": format_value(fmt, entry["value"])}
    return result
