"""Form maps: which box of a safety form takes which shared fact (templates/forms/*.yaml).

One incident record → many forms: each form only says where each fact goes; the facts are found once.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from vff.boxes import Box
from vff.formats import format_value
from vff.options import match_option
from vff.paths import FORMS_DIR, TEMPLATES_DIR
from vff.templates import MULTI_SEPARATOR, load_template

FACTS_PATH = TEMPLATES_DIR / "incident_facts.yaml"
SPECIAL_FACTS = frozenset({"today"})  # the date the form is filled in
SENSITIVE = re.compile(r"\b(ssn|social security)\b", re.IGNORECASE)

Picker = Callable[[str, str, tuple[str, ...]], str]  # (box description, fact value, options) → option or ""


@dataclass(frozen=True)
class FormBox:
    box: str
    facts: tuple[str, ...] = ()
    states: dict[str, str] = field(default_factory=dict)  # fact value → radio state, e.g. {"Male": "/M"}
    tick_if: str = ""  # checkbox: ticked when the fact includes this option
    by_hand: bool = False  # never filled by the app (e.g. SSN)
    format: str = ""


@dataclass(frozen=True)
class FormMap:
    id: str
    title: str
    pdf_path: Path | None
    applies_when: tuple[str, ...]  # kinds of incident this form is for; empty = always
    boxes: tuple[FormBox, ...]
    status: str = "draft"  # draft (auto-made, not yet reviewed) | approved


@dataclass(frozen=True)
class FilledForm:
    values: dict[str, str]  # PDF box name → value ("/On" style for buttons)
    notes: list[tuple[str, str]]  # (box, what to check)
    by_hand: list[str]  # boxes the user must fill in themself


INJURY_FACTS = ("body_parts", "injury_description", "injury_nature")  # someone was hurt


def applies(form: FormMap, facts: dict[str, str]) -> bool:
    said = {t.strip().lower() for t in facts.get("incident_types", "").split(MULTI_SEPARATOR) if t.strip()}
    if not form.applies_when or not said:
        return True
    if any(kind.lower() in said for kind in form.applies_when):
        return True
    # the AI may tag a crash "Vehicle" only although someone was hurt ("his neck was sore"): injury forms still apply
    injury_form = "injury" in {kind.lower() for kind in form.applies_when}
    return injury_form and any(facts.get(key) for key in INJURY_FACTS)


def _state_name(state: str) -> str:
    return re.sub(r"_\d+$", "", state.lstrip("/")).lower()


def _radio(box: Box, form_box: FormBox, value: str) -> str:
    mapped = {k.lower(): v for k, v in form_box.states.items()}.get(value.lower())
    if mapped in box.states:
        return mapped
    said = value.lower()
    for state in box.states:
        name = _state_name(state)
        if name == said or (len(name) == 1 and said.startswith(name)):  # "Yes" → /Y
            return state
    return ""


def _checkbox(box: Box, form_box: FormBox, value: str) -> str:
    on = box.states[0] if box.states else "/Yes"
    picked = {v.strip().lower() for v in value.split(MULTI_SEPARATOR)}
    wanted = form_box.tick_if.lower() if form_box.tick_if else "yes"
    return on if wanted in picked else ""


def _is_code_list(options: tuple[str, ...]) -> bool:
    """Official code lists ("55 Ankle", "29 Fall from same level") must never get free text."""
    return bool(options) and sum(bool(re.match(r"^\d+\s", o)) for o in options) > len(options) / 2


def _choice(box: Box, value: str, picker: Picker | None) -> tuple[str, str]:
    """(value to write, note). A clear match is filled; anything else is left for the user — never guessed."""
    option, _ = match_option(value, box.options)
    if not option and picker:
        option = picker(box.tooltip or box.name, value, box.options)
        option = option if option in box.options else ""
    if option:
        same = option.strip().lower() == value.strip().lower()
        return option, "" if same else f"picked {option!r} for {value!r} — check"
    if box.editable and not _is_code_list(box.options):
        return value, "typed in (not on the form's list)"
    return "", f"pick by hand — nothing on the list clearly matches {value!r}"


def _value(form_box: FormBox, facts: dict[str, str], today: str) -> str:
    parts = [today if key == "today" else facts.get(key, "") for key in form_box.facts]
    return " ".join(p.strip() for p in parts if p and p.strip())


def form_values(form: FormMap, facts: dict[str, str], boxes: dict[str, Box], today: str,
                picker: Picker | None = None) -> FilledForm:
    """What to write into each box of `form` from the shared facts."""
    values, notes, by_hand = {}, [], []
    for form_box in form.boxes:
        box = boxes.get(form_box.box)
        if box is None:
            notes.append((form_box.box, "box not found in the PDF"))
            continue
        if form_box.by_hand or SENSITIVE.search(f"{box.name} {box.tooltip}"):
            by_hand.append(form_box.box)
            continue
        value = _value(form_box, facts, today)
        if box.kind == "signature" or not value:
            continue
        written, note = value, ""
        if box.kind == "text":
            written = format_value(form_box.format, value)
        elif box.kind == "radio":
            written = _radio(box, form_box, value)
        elif box.kind == "checkbox":
            written = _checkbox(box, form_box, value)
        elif box.kind == "choice":
            written, note = _choice(box, value, picker)
        if written:
            values[form_box.box] = written
        if note:
            notes.append((form_box.box, note))
    return FilledForm(values, notes, by_hand)


def _parse_box(raw: dict, known: set[str], path: Path) -> FormBox:
    facts = raw.get("fact", [])
    facts = (facts,) if isinstance(facts, str) else tuple(facts)
    unknown = [f for f in facts if f not in known]
    if unknown:
        raise ValueError(f"{path.name}: box {raw.get('box')!r} uses unknown fact(s) {unknown}")
    return FormBox(
        box=str(raw["box"]),
        facts=facts,
        states={str(k): str(v) for k, v in (raw.get("states") or {}).items()},
        tick_if=str(raw.get("tick_if", "")),
        by_hand=bool(raw.get("by_hand", False)),
        format=str(raw.get("format", "")),
    )


def load_form(path: Path, facts_path: Path = FACTS_PATH) -> FormMap:
    """Read and check one form map."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for required in ("id", "title", "boxes"):
        if required not in raw:
            raise ValueError(f"{path.name}: missing {required!r}")
    known = {f.key for f in load_template(facts_path).fields} | SPECIAL_FACTS
    pdf = (path.parent / raw["pdf"]).resolve() if raw.get("pdf") else None
    if pdf is not None and not pdf.exists():
        raise ValueError(f"{path.name}: PDF not found at {pdf}")
    return FormMap(
        id=str(raw["id"]),
        title=str(raw["title"]),
        pdf_path=pdf,
        applies_when=tuple(str(k) for k in raw.get("applies_when", [])),
        boxes=tuple(_parse_box(b, known, path) for b in raw["boxes"]),
        status=str(raw.get("status", "draft")),
    )


def load_forms(folder: Path = FORMS_DIR) -> list[FormMap]:
    return [load_form(p) for p in sorted(Path(folder).glob("*.yaml"))]
