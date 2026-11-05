"""Write approved answers into the boxes of a fillable PDF. The blank form is never changed."""

import os
import re
import textwrap
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject

from vff.storage import FILE_MODE

MULTILINE_FLAG = 1 << 12  # PDF spec: text box may hold several lines
AVG_CHAR_WIDTH = 0.52  # average character width, as a share of the font size (Helvetica)
DEFAULT_FONT_SIZE = 12.0  # what viewers use when a box says "auto" (size 0)


def _font_size(widget) -> float:
    """The box's own text size, from its /DA ("/Helv 7 Tf …"); auto (0) or missing → 12 pt."""
    match = re.search(r"([\d.]+)\s+Tf", str(_inherited(widget, "/DA", "")))
    size = float(match.group(1)) if match else 0.0
    return size or DEFAULT_FONT_SIZE


def _multiline_widths(writer: PdfWriter) -> dict[str, int]:
    """Characters per line for each multi-line text box, from the box's width on the page."""
    widths = {}
    for page in writer.pages:
        for annot in page.get("/Annots", []) or []:
            widget = annot.get_object()
            name = _widget_name(widget)
            flags = int(widget.get("/Ff", widget.get("/Parent", {}).get("/Ff", 0)))
            if name and flags & MULTILINE_FLAG:
                x0, _, x1, _ = (float(v) for v in widget["/Rect"])
                widths[name] = max(20, int(abs(x1 - x0) / (AVG_CHAR_WIDTH * _font_size(widget))))
    return widths


def _wrap(values: dict[str, str], widths: dict[str, int]) -> dict[str, str]:
    """PDF libraries draw text on one line; add line breaks so long answers stay inside the box."""
    return {
        name: "\n".join(textwrap.wrap(value, widths[name])) if name in widths else value
        for name, value in values.items()
    }


def _save_private(writer: PdfWriter, out: Path) -> Path:
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "wb") as f:
        writer.write(f)
    return Path(out)


def _widget_name(widget) -> str:
    """The box's full name, every level joined ("Item.Gender"), as the form's field list names it."""
    parts, node = [], widget
    while node is not None:
        node = node.get_object()
        if "/T" in node:
            parts.append(str(node["/T"]))
        node = node.get("/Parent")
    return ".".join(reversed(parts))


RADIO_FLAG = 1 << 15  # PDF spec: round button, pick one of a group
PUSHBUTTON_FLAG = 1 << 16  # PDF spec: a button you press ("Reset"), never an answer
# The mark the form itself asks for (/MK /CA, a ZapfDingbats character)
FORM_MARKS = {"l": "dot", "4": "check", "5": "cross", "8": "cross", "n": "square"}


def _inherited(widget, key: str, default=None):
    """A widget's own setting, or its parent field's (radio groups keep /FT and /Ff on the parent)."""
    if key in widget:
        return widget[key]
    parent = widget.get("/Parent")
    return parent.get_object().get(key, default) if parent else default


def mark_style(widget) -> str | None:
    """'dot' | 'check' | 'cross' | 'square' for a box that can be ticked; None for anything else."""
    flags = int(_inherited(widget, "/Ff", 0))
    if _inherited(widget, "/FT") != "/Btn" or flags & PUSHBUTTON_FLAG:
        return None
    asked = FORM_MARKS.get(str(widget.get("/MK", {}).get("/CA", "")))
    return asked or ("dot" if flags & RADIO_FLAG else "check")


def choice_marks(page, values: dict[str, str]) -> list[tuple[str, tuple[float, ...], str]]:
    """(state, box rectangle, mark style) for every box whose 'on' state is the chosen answer."""
    marks = []
    for annot in page.get("/Annots", []) or []:
        widget = annot.get_object()
        style = mark_style(widget)
        chosen = values.get(_widget_name(widget), "")
        if style is None or not chosen.startswith("/"):
            continue
        states = set(widget.get("/AP", {}).get("/N", {}).keys()) - {"/Off"}
        if chosen in states:
            marks.append((chosen, tuple(float(v) for v in widget["/Rect"]), style))
    return marks


def _circle(cx: float, cy: float, r: float) -> str:
    k = 0.5523 * r  # Bézier handle length for a circle
    return (f"{cx + r:.2f} {cy:.2f} m {cx + r:.2f} {cy + k:.2f} {cx + k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c "
            f"{cx - k:.2f} {cy + r:.2f} {cx - r:.2f} {cy + k:.2f} {cx - r:.2f} {cy:.2f} c "
            f"{cx - r:.2f} {cy - k:.2f} {cx - k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
            f"{cx + k:.2f} {cy - r:.2f} {cx + r:.2f} {cy - k:.2f} {cx + r:.2f} {cy:.2f} c f")


def draw_commands(style: str, rect: tuple[float, ...]) -> str:
    """PDF drawing commands for one mark, sized to the middle of its box."""
    x0, y0, x1, y1 = min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])
    size = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left, right, low, high = cx - size * 0.3, cx + size * 0.3, cy - size * 0.3, cy + size * 0.3
    pen = f"{size * 0.12:.2f} w 1 J 1 j "
    if style == "dot":
        return _circle(cx, cy, size * 0.3)
    if style == "check":
        return (pen + f"{left:.2f} {cy:.2f} m {cx - size * 0.08:.2f} {low:.2f} l {right:.2f} {high:.2f} l S")
    if style == "cross":
        return pen + f"{left:.2f} {low:.2f} m {right:.2f} {high:.2f} l {left:.2f} {high:.2f} m {right:.2f} {low:.2f} l S"
    return f"{left:.2f} {low:.2f} {right - left:.2f} {high - low:.2f} re f"  # square


def box_drawings(page, choices: dict[str, str]) -> list[tuple[str, object, tuple[float, ...]]]:
    """(state, the form's own drawing of that state, box rectangle) for every box that can be ticked:
    the chosen box gets its 'on' drawing (dot, check, X, filled square — whatever the form uses), the rest 'off'."""
    drawings = []
    for annot in page.get("/Annots", []) or []:
        widget = annot.get_object()
        if mark_style(widget) is None:
            continue
        pictures = widget.get("/AP", {}).get("/N", {})
        chosen = choices.get(_widget_name(widget), "")
        state = chosen if chosen in pictures and chosen != "/Off" else "/Off"
        if state in pictures:
            drawings.append((state, pictures.raw_get(state), tuple(float(v) for v in widget["/Rect"])))
    return drawings


def empty_boxes(page) -> list[tuple[object, tuple[float, ...]]]:
    """(the form's own 'unticked' drawing, box rectangle) for every box that can be ticked."""
    return [(picture, rect) for _, picture, rect in box_drawings(page, {})]


def _has_ink(picture) -> bool:
    return bool(picture.get_object().get_data().strip())


def _draw_boxes(page, drawings, marks) -> None:
    """Draw every box the way the form itself draws it; our own mark only if the form's 'on' picture is empty."""
    if not drawings:
        return
    overlay = PdfWriter().add_blank_page(float(page.mediabox.width), float(page.mediabox.height))
    xobjects = DictionaryObject()
    ops = []
    for i, (state, picture, rect) in enumerate(drawings):
        name = NameObject(f"/Box{i}")
        xobjects[name] = picture
        bbox = picture.get_object().get("/BBox", [0, 0, 0, 0])
        dx, dy = min(rect[0], rect[2]) - float(bbox[0]), min(rect[1], rect[3]) - float(bbox[1])
        ops.append(f"q 1 0 0 1 {dx:.2f} {dy:.2f} cm {name} Do Q")
        if state != "/Off" and not _has_ink(picture):
            style = next(style for chosen, box, style in marks if box == rect)
            ops.append(f"q 0 g 0 G {draw_commands(style, rect)} Q")
    stream = DecodedStreamObject()
    stream.set_data(" ".join(ops).encode())
    overlay[NameObject("/Contents")] = stream
    overlay[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): xobjects})
    page.merge_page(overlay)


HIDDEN_FLAG = 1 << 1  # PDF spec: a box the form never shows


def tidy_rects(writer: PdfWriter) -> None:
    """Put every box rectangle right way up (left, bottom, right, top); some forms store top before bottom."""
    for page in writer.pages:
        for annot in page.get("/Annots", []) or []:
            widget = annot.get_object()
            if "/Rect" not in widget:
                continue
            x0, y0, x1, y1 = (float(v) for v in widget["/Rect"])
            widget[NameObject("/Rect")] = ArrayObject(
                FloatObject(v) for v in (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))


def _hidden_boxes(writer: PdfWriter) -> set[str]:
    return {_widget_name(annot.get_object()) for page in writer.pages for annot in page.get("/Annots", []) or []
            if int(annot.get_object().get("/F", 0)) & HIDDEN_FLAG}


def print_pdf(blank: Path, values: dict[str, str], out: Path) -> Path:
    """Save a print copy: answers drawn onto the page, no editable boxes, so every viewer shows the same thing."""
    writer = PdfWriter(clone_from=str(blank))
    tidy_rects(writer)
    hidden = _hidden_boxes(writer)
    # pypdf draws a straight apostrophe as "©" with some forms' fonts; the curly one draws right
    text = {k: v.replace("'", "\u2019") for k, v in values.items() if not v.startswith("/") and k not in hidden}
    text = _wrap(text, _multiline_widths(writer))
    choices = {k: v for k, v in values.items() if v.startswith("/")}
    for page in writer.pages:
        if not page.get("/Annots"):
            continue  # a page with no boxes (e.g. the SD form's instructions page)
        drawings, marks = box_drawings(page, choices), choice_marks(page, choices)
        writer.update_page_form_field_values(page, text, auto_regenerate=False, flatten=True)
        _draw_boxes(page, drawings, marks)
    writer.remove_annotations(subtypes="/Widget")
    del writer.root_object[NameObject("/AcroForm")]
    return _save_private(writer, out)
