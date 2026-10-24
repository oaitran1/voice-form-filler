"""Every saved report → one Excel workbook (data_tracker/reports.xlsx): a sheet per form, a row per report, a column for
every box on the page. Spoken reports (records/<date>_incident/*_filled.pdf) and old PDFs (copied into
records/old_pdfs/) go in the same workbook; the Source column says which is which.

Reads the answer stored in each box — no AI, nothing guessed, nothing leaves the Mac. Which box is which question
is written once per form in the `excel:` part of templates/forms/<form>.yaml, in the paper's order, under the
paper's section titles. The workbook is rebuilt from the PDFs each time, so it always matches them.
A PDF that can't be read, or isn't one of those forms, goes on the "Not exported" sheet — never silently dropped.
"""

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from pypdf.errors import PyPdfError

from vff.boxes import open_pdf
from vff.paths import DATA_TRACKER_DIR, FORMS_DIR, RECORDS_DIR
from vff.storage import FILE_MODE, private_folder

WORKBOOK = DATA_TRACKER_DIR / "reports.xlsx"  # the real one; a live test writes data_tracker/live_test.xlsx
OLD_PDFS = "old_pdfs"  # old filled PDFs, copied in once by `uv run add-old-pdfs`
SPOKEN, OLD = "spoken report", "old PDF"
MIN_MATCH = 0.5  # share of a form's boxes a PDF must have to count as that form
OFF = frozenset({"", "/Off", "Off"})
CHECK_COLUMN = "Check by hand"
PROBLEM_SHEET = "Not exported"
MAX_WIDTH = 50


@dataclass(frozen=True)
class Column:
    box: str
    label: str
    words: dict[str, str] = field(default_factory=dict)  # stored button state → word in the cell, e.g. /M → Male


@dataclass(frozen=True)
class Section:
    title: str
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Layout:
    form: str
    sheet: str
    sections: tuple[Section, ...]
    copies: re.Pattern | None = None  # names of boxes on pages added inside the same PDF ("Add a Form Page")
    copy_prefix: str = ""  # copy box "Full name" → this form's box "301 Full name"
    blank: dict[str, str] = field(default_factory=dict)  # what each box holds on the blank form (not an answer)

    @property
    def columns(self) -> tuple[Column, ...]:
        return tuple(c for s in self.sections for c in s.columns)


@dataclass(frozen=True)
class Report:
    file: str
    source: str  # SPOKEN or OLD
    number: int  # 1 = the form's own page; 2, 3, … = pages added inside the same PDF
    values: dict[str, str]  # box → cell text
    unknown: dict[str, str]  # filled boxes no column is for


# ---------- layouts ----------

def _column(entry: dict, where: str) -> Column:
    if not isinstance(entry, dict) or not entry.get("box") or not entry.get("label"):
        raise ValueError(f"{where}: every column needs a box and a label, got {entry!r}")
    words = entry.get("words") or {}
    if any(isinstance(v, bool) for v in words.values()):
        raise ValueError(f"{where}: put quotes around Yes / No in the words of {entry['box']!r} (YAML reads them as true/false)")
    words = {str(k): str(v) for k, v in words.items()}
    return Column(str(entry["box"]), str(entry["label"]), words)


def load_layout(path: Path) -> Layout:
    """The Excel columns of one form: the `excel:` part of its form file (templates/forms/<form>.yaml)."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    data = raw.get("excel") or {}
    for key, value in (("id", raw.get("id")), ("excel.sheet", data.get("sheet")), ("excel.sections", data.get("sections"))):
        if not value:
            raise ValueError(f"{path.name}: missing '{key}'")
    sections = tuple(
        Section(str(s.get("title", "")), tuple(_column(c, path.name) for c in s.get("columns") or ()))
        for s in data["sections"])
    seen: set[str] = set()
    for column in (c for s in sections for c in s.columns):
        if column.box in seen:
            raise ValueError(f"{path.name}: box {column.box!r} is listed twice")
        seen.add(column.box)
    copies = re.compile(data["copies"]) if data.get("copies") else None
    blank = read_pdf(path.parent / raw["pdf"]) if raw.get("pdf") else {}  # what boxes hold before anyone types
    return Layout(str(raw["id"]), str(data["sheet"])[:31], sections, copies, str(data.get("copy_prefix", "")),
                  blank)


def load_layouts(folder: Path = FORMS_DIR) -> list[Layout]:
    """Every form that has Excel columns."""
    paths = sorted(Path(folder).glob("*.yaml"))
    return [load_layout(p) for p in paths if "excel" in (yaml.safe_load(p.read_text()) or {})]


# ---------- reading a PDF ----------

def _text(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return "" if value is None else str(value)


def read_pdf(path: Path) -> dict[str, str]:
    """Every box's stored answer, by the box's full name. Raises ValueError when the file can't be read."""
    try:
        fields = open_pdf(path).get_fields() or {}
    except (PyPdfError, OSError, ValueError, KeyError) as err:
        raise ValueError(f"can't open it ({err.__class__.__name__}: {err})") from err
    return {str(name): _text(f.get("/V")) for name, f in fields.items()}


def _answered(layout: Layout, box: str, raw: str) -> bool:
    """Typed or ticked by someone: not off, not only spaces, not what the blank form already held."""
    return raw not in OFF and bool(raw.strip()) and raw != layout.blank.get(box)


def _cell(column: Column, raw: str) -> str:
    if raw.startswith("/"):
        return column.words.get(raw, raw[1:])
    return raw


def match_layout(values: dict[str, str], layouts: list[Layout]) -> Layout | None:
    """The form this PDF is: the layout whose boxes it has the most of (at least MIN_MATCH of them)."""
    def share(layout: Layout) -> float:
        boxes = {c.box for c in layout.columns}
        return len(boxes & values.keys()) / len(boxes)
    best = max(layouts, key=share, default=None)
    return best if best is not None and share(best) >= MIN_MATCH else None


def _values(raw: dict[str, str], layout: Layout) -> dict[str, str]:
    return {c.box: _cell(c, raw[c.box]) if _answered(layout, c.box, raw.get(c.box, "")) else ""
            for c in layout.columns}


def reports_from(file: str, values: dict[str, str], layout: Layout, source: str = OLD) -> list[Report]:
    """One report for the form's own page, plus one per added page; empty reports are left out."""
    known = {c.box for c in layout.columns}
    pages: dict[int, dict[str, str]] = {}
    unknown = {}
    for name, value in values.items():
        found = layout.copies.fullmatch(name) if layout.copies else None
        if found:
            pages.setdefault(int(found["page"]), {})[layout.copy_prefix + found["box"]] = value
        elif name not in known and _answered(layout, name, value):
            unknown[name] = value
    reports = [Report(file, source, 1, _values(values, layout), unknown)]
    reports += [Report(file, source, i, _values(pages[page], layout), {})
                for i, page in enumerate(sorted(pages), start=2)]
    return [r for r in reports if any(r.values.values()) or r.unknown]


# ---------- which PDFs go in ----------

def saved_pdfs(records_dir: Path = RECORDS_DIR) -> list[tuple[Path, str]]:
    """(PDF, source) for every saved report: the editable copy of each spoken report, then every old PDF.
    Print copies have no boxes left, so only the *_filled.pdf of a spoken report is read."""
    records_dir = Path(records_dir)
    spoken = sorted(p for p in records_dir.glob("*/*_filled.pdf") if p.parent.name != OLD_PDFS)
    old = sorted(p for p in (records_dir / OLD_PDFS).glob("*") if p.suffix.lower() == ".pdf")
    return [(p, SPOKEN) for p in spoken] + [(p, OLD) for p in old]


def _pdfs_in(paths: list[Path]) -> list[Path]:
    found = []
    for path in map(Path, paths):
        if not path.exists():
            raise FileNotFoundError(f"No file or folder at {path}")
        found += sorted(p for p in path.rglob("*") if p.suffix.lower() == ".pdf") if path.is_dir() else [path]
    return found


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _free_name(folder: Path, name: str) -> Path:
    target, n = folder / name, 2
    while target.exists():
        target, n = folder / f"{Path(name).stem}_{n}{Path(name).suffix}", n + 1
    return target


def add_old_pdfs(paths: list[Path], records_dir: Path = RECORDS_DIR) -> tuple[list[Path], list[Path]]:
    """Copy old filled PDFs (files or folders) into records/old_pdfs/. The originals are not touched.
    A file already copied (same contents) is skipped; a different file with the same name is kept as name_2.pdf.
    Returns (copied, skipped)."""
    pdfs = _pdfs_in(paths)
    folder = private_folder(Path(records_dir) / OLD_PDFS)
    have = {_digest(p) for p in folder.glob("*") if p.is_file()}
    added, skipped = [], []
    for pdf in pdfs:
        digest = _digest(pdf)
        if digest in have:
            skipped.append(pdf)
            continue
        target = _free_name(folder, pdf.name)
        shutil.copyfile(pdf, target)
        target.chmod(FILE_MODE)
        have.add(digest)
        added.append(target)
    return added, skipped


# ---------- the workbook ----------

def _put(sheet, row: int, col: int, value) -> None:
    text = ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value
    cell = sheet.cell(row=row, column=col, value=text)
    if isinstance(value, str):
        cell.data_type = "s"  # always plain text: "=…" in a box is never run as a formula, "02134" keeps its 0
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def _fit_widths(sheet, skip_rows: int = 0) -> None:
    for i, cells in enumerate(sheet.iter_cols(min_row=skip_rows + 1), start=1):
        longest = max((len(line) for c in cells if c.value is not None for line in str(c.value).splitlines()),
                      default=8)
        sheet.column_dimensions[get_column_letter(i)].width = min(max(longest, 8), MAX_WIDTH) + 2


FIXED = ("Source", "File", "Report")


def _write_form_sheet(sheet, layout: Layout, reports: list[Report]) -> None:
    col = len(FIXED) + 1
    for section in layout.sections:
        _put(sheet, 1, col, section.title)
        if len(section.columns) > 1:
            sheet.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(section.columns) - 1)
        col += len(section.columns)
    for i, label in enumerate([*FIXED] + [c.label for c in layout.columns] + [CHECK_COLUMN], start=1):
        _put(sheet, 2, i, label)
    for r, report in enumerate(reports, start=3):
        check = "; ".join(f"{name} = {value}" for name, value in report.unknown.items())
        cells = [report.source, report.file, report.number] + [report.values[c.box] for c in layout.columns] + [check]
        for i, value in enumerate(cells, start=1):
            _put(sheet, r, i, value)
    for row in (1, 2):
        for cell in sheet[row]:
            cell.font = Font(bold=True)
    sheet.freeze_panes = sheet.cell(row=3, column=len(FIXED) + 1).coordinate
    _fit_widths(sheet, skip_rows=1)  # section titles span many columns; size by labels and answers


def _write_problem_sheet(sheet, problems: list[tuple[str, str, str]]) -> None:
    for r, row in enumerate([("Source", "File", "Why it was not exported")] + problems, start=1):
        for i, value in enumerate(row, start=1):
            _put(sheet, r, i, value)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    _fit_widths(sheet)


def _save_replacing(workbook: Workbook, out: Path) -> None:
    """Write next to `out`, then swap it in: a crash never leaves a half-written workbook. Owner-only."""
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=f".{out.stem}-", suffix=".xlsx")  # created owner-only
    try:
        with os.fdopen(fd, "wb") as f:
            workbook.save(f)
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _sort(pdfs: list[tuple[Path, str]], records_dir: Path, layouts: list[Layout]):
    rows: dict[str, list[Report]] = {layout.sheet: [] for layout in layouts}
    problems: list[tuple[str, str, str]] = []
    names = ", ".join(layout.sheet for layout in layouts)
    for pdf, source in pdfs:
        shown = pdf.relative_to(records_dir).as_posix()
        try:
            values = read_pdf(pdf)
        except ValueError as err:
            problems.append((source, shown, f"{err} — check by hand"))
            continue
        layout = match_layout(values, layouts) if values else None
        if not values:
            problems.append((source, shown, "no fillable boxes (scanned or flattened PDF) — check by hand"))
        elif layout is None:
            problems.append((source, shown, f"not one of the forms this exports ({names}) — check by hand"))
        elif found := reports_from(shown, values, layout, source):
            rows[layout.sheet] += found
        else:
            problems.append((source, shown, f"{layout.sheet} with no answers in any box"))
    return rows, problems


def rebuild_workbook(records_dir: Path = RECORDS_DIR, layouts: list[Layout] | None = None,
                     out: Path = WORKBOOK) -> tuple[Path, dict[str, int]]:
    """Rebuild the workbook `out` (data_tracker/reports.xlsx) from every saved report in `records_dir`, spoken and
    old. Returns (path, rows per sheet)."""
    records_dir = private_folder(Path(records_dir))
    layouts = load_layouts() if layouts is None else layouts
    rows, problems = _sort(saved_pdfs(records_dir), records_dir, layouts)
    workbook = Workbook()
    workbook.remove(workbook.active)
    for layout in layouts:
        _write_form_sheet(workbook.create_sheet(layout.sheet), layout, rows[layout.sheet])
    summary = {sheet: len(found) for sheet, found in rows.items()}
    if problems:
        _write_problem_sheet(workbook.create_sheet(PROBLEM_SHEET), problems)
        summary[PROBLEM_SHEET] = len(problems)
    out = Path(out)
    private_folder(out.parent)
    _save_replacing(workbook, out)
    return out, summary
