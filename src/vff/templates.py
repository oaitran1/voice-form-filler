"""Templates: a list of fields to find in a story — templates/incident_facts.yaml is the one the app uses.

Each field says what it is (a date, a time, a choice …) and how it must be written; forms then take these facts.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


# short: a name, number, place …  date/time: as spoken  choice: one of `options`
# text: a written section ("What happened?"), 1–3 sentences from the recording
# multi: any number of `options` ("check all that apply"), written "Rainy; Fog"
KINDS = frozenset({"short", "date", "time", "choice", "multi", "text"})
GROUPS = frozenset({"story", "company", "mishap"})  # story: said in the recording; company: saved profile, unless the
# company name is said; mishap: military (Navy / DoD) facts, asked as their own question, blank for a civilian workplace
MULTI_SEPARATOR = ";"


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "short"
    pdf_field: str = ""
    options: tuple[str, ...] = ()
    hint: str = ""
    no_names: bool = False  # the form forbids names / personal identifiers in this box
    time_of: str = ""  # an AM/PM box: the key of the time field it belongs to
    format: str = ""  # how the box wants it written: mm/dd/yyyy, state, zip, phone (see vff/formats.py)
    group: str = "story"


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    description: str
    pdf_path: Path | None
    fields: tuple[Field, ...]
    rules: tuple[str, ...] = ()  # the form's own instructions, e.g. "no names in boxes 14–17"
    intro: str = ""  # said before recording: what this form is and what to talk about

    def field(self, key: str) -> Field:
        return next(f for f in self.fields if f.key == key)


def _parse_field(raw: dict) -> Field:
    field = Field(
        key=str(raw["key"]),
        label=str(raw["label"]),
        kind=str(raw.get("kind", "short")),
        pdf_field=str(raw.get("pdf_field", "")),
        options=tuple(str(o) for o in raw.get("options", [])),
        hint=str(raw.get("hint", "")),
        no_names=bool(raw.get("no_names", False)),
        time_of=str(raw.get("time_of", "")),
        format=str(raw.get("format", "")),
        group=str(raw.get("group", "story")),
    )
    if field.kind not in KINDS:
        raise ValueError(f"Field {field.key!r}: unknown kind {field.kind!r} (use one of {sorted(KINDS)})")
    if field.kind in ("choice", "multi") and not field.options:
        raise ValueError(f"Field {field.key!r}: a {field.kind} field needs options")
    if field.group not in GROUPS:
        raise ValueError(f"Field {field.key!r}: unknown group {field.group!r} (use one of {sorted(GROUPS)})")
    return field


def load_template(path: Path) -> Template:
    """Read and validate one template file."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f", line {mark.line + 1}" if mark else ""
        raise ValueError(f"{path.name} is not valid YAML ({getattr(err, 'problem', err)}{where})") from err
    for required in ("id", "title", "fields"):
        if required not in raw:
            raise ValueError(f"{path.name}: missing {required!r}")

    fields = tuple(_parse_field(f) for f in raw["fields"])
    keys = [f.key for f in fields]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"{path.name}: duplicate field keys {duplicates}")

    kinds = {f.key: f.kind for f in fields}
    for field in fields:
        if field.time_of and kinds.get(field.time_of) != "time":
            raise ValueError(f"{path.name}: {field.key!r} time_of {field.time_of!r} is not a time field")

    pdf = raw.get("pdf")
    pdf_path = (path.parent / pdf).resolve() if pdf else None
    if pdf_path is not None and not pdf_path.exists():
        raise ValueError(f"{path.name}: PDF not found at {pdf_path}")

    rules = tuple(str(r) for r in raw.get("rules", []))
    return Template(
        str(raw["id"]), str(raw["title"]), str(raw.get("description", "")), pdf_path, fields, rules,
        intro=" ".join(str(raw.get("intro", "")).split()),
    )


def briefing(template: Template) -> str:
    """What to tell the user before they start talking, so they know what to cover."""
    if template.intro:
        return template.intro
    return f"This is the {template.title}. {template.description}".strip()
