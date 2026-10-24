"""Live test: you read a script out loud, the app fills the forms the normal way, and every box is checked against
the script's right answers (live_test/scripts/*.yaml). Results: live_test/results/<date_time>/RESULTS.md.

A script's right answers are written as facts ("person_first_name: Marcus"); the app's own box rules turn them into
what each box should hold, so every box of every form is checked. Written sections ("What happened?") can't be
word-for-word, so they are shown for you to read, not scored.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from vff.boxes import read_boxes
from vff.export_excel import Layout, _answered, _cell, load_layouts, read_pdf
from vff.forms import FormMap, applies, form_values, load_forms
from vff.incident import story_template, with_company
from vff.paths import DATA_TRACKER_DIR, ROOT, TEMPLATES_DIR

SCRIPTS_DIR = ROOT / "live_test" / "scripts"
RESULTS_DIR = ROOT / "live_test" / "results"
TEST_WORKBOOK = DATA_TRACKER_DIR / "live_test.xlsx"  # the latest live test; never mixed with real reports
TEST_PROFILE = TEMPLATES_DIR / "examples" / "company_profile.yaml"  # same company every run, so answers are known
READ_BY_EYE = frozenset({"injury_cause"})  # short, but said many ways ("wet floor", "the wet kitchen floor")
RIGHT, WRONG, LOOK = "✓", "✗", "👁"


@dataclass(frozen=True)
class Script:
    id: str
    title: str
    text: str
    hints: str
    facts: dict[str, str]


@dataclass(frozen=True)
class BoxCheck:
    label: str
    expected: str
    got: str
    verdict: str  # RIGHT, WRONG or LOOK


@dataclass(frozen=True)
class FormCheck:
    title: str
    filled: bool  # did the app fill this form at all
    boxes: tuple[BoxCheck, ...]

    def count(self, verdict: str) -> int:
        return sum(b.verdict == verdict for b in self.boxes)


def load_scripts(folder: Path = SCRIPTS_DIR) -> list[Script]:
    known = {f.key for f in story_template().fields}
    scripts = []
    for path in sorted(Path(folder).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text()) or {}
        for key in ("title", "script", "facts"):
            if not raw.get(key):
                raise ValueError(f"{path.name}: missing '{key}'")
        facts = {str(k): str(v) for k, v in raw["facts"].items()}
        if unknown := sorted(set(facts) - known):
            raise ValueError(f"{path.name}: not facts the app knows: {', '.join(unknown)}")
        scripts.append(Script(path.stem, str(raw["title"]), " ".join(str(raw["script"]).split()),
                              str(raw.get("hints", "")), facts))
    return scripts


def _by_eye_boxes(form: FormMap) -> set[str]:
    written = {f.key for f in story_template().fields if f.kind == "text"} | READ_BY_EYE
    return {b.box for b in form.boxes if set(b.facts) & written}


def _same(a: str, b: str) -> bool:
    def norm(v: str) -> str:
        # long answers wrap onto several lines in the PDF; "R." and "R" are the same initial
        return " ".join(v.replace(".", " ").split()).casefold()
    return norm(a) == norm(b)


def _check_form(form: FormMap, expected: dict[str, str], pdf: Path | None, layout: Layout | None) -> FormCheck:
    got = read_pdf(pdf) if pdf else {}
    columns = {c.box: c for c in layout.columns} if layout else {}
    order = list(columns) + [b.box for b in form.boxes if b.box not in columns]
    by_eye = _by_eye_boxes(form)
    checks = []
    for box in order:
        want = expected.get(box, "")
        have = got.get(box, "") if layout is None or _answered(layout, box, got.get(box, "")) else ""
        if not want and not have:
            continue
        column = columns.get(box)
        show = (lambda v: _cell(column, v)) if column else (lambda v: v)
        verdict = LOOK if box in by_eye else RIGHT if _same(want, have) else WRONG
        checks.append(BoxCheck(column.label if column else box, show(want) if want else "", show(have) if have else "",
                               verdict))
    return FormCheck(form.title, pdf is not None, tuple(checks))


def check_report(script: Script, folder: Path, profile: dict[str, str], today: str) -> list[FormCheck]:
    """Every form the script's story should fill (and any the app filled anyway), box by box."""
    facts = with_company(script.facts, profile)
    layouts = {layout.form: layout for layout in load_layouts()}
    checks = []
    for form in load_forms():
        pdf = folder / f"{form.id}_filled.pdf"
        should = applies(form, facts)
        if not should and not pdf.exists():
            continue
        boxes = {b.name: b for b in read_boxes(form.pdf_path)}
        expected = form_values(form, facts, boxes, today).values if should else {}
        checks.append(_check_form(form, expected, pdf if pdf.exists() else None, layouts.get(form.id)))
    return checks


# ---------- RESULTS.md ----------

def _cell_md(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|") or "—"


def write_results(run_dir: Path, rows: list[tuple[Script, str, Path | None, list[FormCheck]]],
                  started: datetime) -> tuple[Path, int, int, int]:
    """rows = (script, what the app heard, saved folder, form checks). Returns (path, right, wrong, look)."""
    right = sum(f.count(RIGHT) for *_, forms in rows for f in forms)
    wrong = sum(f.count(WRONG) for *_, forms in rows for f in forms)
    look = sum(f.count(LOOK) for *_, forms in rows for f in forms)
    scored = right + wrong
    lines = [f"# Live test — {started:%Y-%m-%d %H:%M}", "",
             (f"**{right} of {scored} boxes right** ({right / scored:.0%})" if scored else "**No boxes checked**")
             + f" · {wrong} wrong · {look} written answers to read by eye.", "",
             f"{RIGHT} right · {WRONG} wrong · {LOOK} read it yourself (written answers can't match word for word)",
             "", "The filled PDFs are in each script's folder; the Excel file is `data_tracker/live_test.xlsx`.", ""]
    for script, heard, folder, forms in rows:
        lines += [f"## {script.id} — {script.title}", ""]
        if folder is None:
            lines += ["Nothing was recorded for this script.", ""]
            continue
        lines += [f"Folder: `{folder.name}/`", "", "**The script:**", f"> {script.text}", "",
                  "**What the app heard:**", f"> {heard}", ""]
        for form in forms:
            if not form.filled:
                lines += [f"### {form.title} — {WRONG} NOT FILLED (it should have been)", ""]
            else:
                lines += [f"### {form.title} — {form.count(RIGHT)} of {form.count(RIGHT) + form.count(WRONG)} right", ""]
            lines += ["| | Box | Should be | App wrote |", "|---|---|---|---|"]
            lines += [f"| {b.verdict} | {_cell_md(b.label)} | {_cell_md(b.expected) if b.verdict != LOOK else '(read it)'} "
                      f"| {_cell_md(b.got)} |" for b in form.boxes]
            lines.append("")
    path = run_dir / "RESULTS.md"
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    return path, right, wrong, look
