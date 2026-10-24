"""Read every fillable box of a PDF form: its name, kind, printed description (tooltip), options and on-states.

This is what the auto-template reads to learn a new form, and what filling uses to write each box correctly.
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

RADIO_FLAG = 1 << 15
PUSHBUTTON_FLAG = 1 << 16
EDITABLE_CHOICE_FLAG = 1 << 18  # a dropdown you may also type into
MULTILINE_FLAG = 1 << 12


@dataclass(frozen=True)
class Box:
    name: str
    kind: str  # text | choice | radio | checkbox | signature
    tooltip: str = ""
    options: tuple[str, ...] = ()  # dropdown: what the user sees
    states: tuple[str, ...] = ()  # radio/checkbox: the "on" states, e.g. ("/Yes", "/No") or ("/On",)
    editable: bool = False  # dropdown that also accepts typed text
    multiline: bool = False


def _kind(field_type: str, flags: int) -> str | None:
    if field_type == "/Tx":
        return "text"
    if field_type == "/Ch":
        return "choice"
    if field_type == "/Sig":
        return "signature"
    if field_type == "/Btn" and not flags & PUSHBUTTON_FLAG:
        return "radio" if flags & RADIO_FLAG else "checkbox"
    return None


def _options(field) -> tuple[str, ...]:
    shown = []
    for option in field.get("/Opt") or []:
        text = option[1] if isinstance(option, list) else option
        if str(text).strip():
            shown.append(str(text).strip())
    return tuple(shown)


def _states(field) -> tuple[str, ...]:
    """'On' states from the field, or from its buttons' drawings when the form keeps them there."""
    states = [s for s in field.get("/_States_", []) if s != "/Off"]
    for kid in field.get("/Kids", []) or []:
        pictures = kid.get_object().get("/AP", {}).get("/N", {})
        states += [s for s in (pictures.keys() if hasattr(pictures, "keys") else []) if s != "/Off"]
    return tuple(dict.fromkeys(str(s) for s in states))


def open_pdf(path: Path) -> PdfReader:
    """Open a form; many government forms are encrypted with an empty password (fill allowed)."""
    reader = PdfReader(path)
    if reader.is_encrypted:
        reader.decrypt("")
    return reader


def read_boxes(pdf_path: Path) -> list[Box]:
    """All fillable boxes of the form, in the form's own order. Push buttons ("Reset") are left out."""
    boxes = []
    for name, field in (open_pdf(pdf_path).get_fields() or {}).items():
        flags = int(field.get("/Ff", 0))
        kind = _kind(str(field.get("/FT", "")), flags)
        if kind is None:
            continue
        states = _states(field) if kind in ("radio", "checkbox") else ()
        if kind == "checkbox" and len(states) > 1:
            kind = "radio"  # a group of buttons, one answer
        boxes.append(Box(
            name=str(name),
            kind=kind,
            tooltip=" ".join(str(field.get("/TU", "")).split()),
            options=_options(field) if kind == "choice" else (),
            states=states,
            editable=kind == "choice" and bool(flags & EDITABLE_CHOICE_FLAG),
            multiline=kind == "text" and bool(flags & MULTILINE_FLAG),
        ))
    return boxes
