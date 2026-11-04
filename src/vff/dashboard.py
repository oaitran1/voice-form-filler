"""The app's dashboard (data_tracker/dashboard.html): the reports filed, the forms, and how accurate the live tests are.

Reads only files the app already writes — records/<report>/record.json + forms.json, and live_test/results/*/RESULTS.md.
One self-contained HTML page, no internet; rewritten after every report and every live test, and it reloads itself.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vff.dashboard_page import PAGE, REDIRECT
from vff.forms import load_forms
from vff.live_test import LOOK, RESULTS_DIR, RIGHT, WRONG
from vff.paths import DATA_TRACKER_DIR, RECORDS_DIR

RUN_TITLE = re.compile(r"^# Live test — (\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
SCRIPT_TITLE = re.compile(r"^## (\S+) — (.+)$")
FORM_TITLE = re.compile(r"^### (.+?) — (?:(\d+) of (\d+) right|✗ NOT FILLED.*)$")
BOX_ROW = re.compile(r"^\| (✓|✗|👁) \| (.+?) \| (.*?) \| (.*?) \|$")
TYPED = "typed"
VOICE = "voice"
DASHBOARD = DATA_TRACKER_DIR / "dashboard.html"
OLD_DASHBOARD = RESULTS_DIR / "dashboard.html"  # where it used to be; now a page that jumps to the new one
STORY_CHARS = 180


@dataclass(frozen=True)
class Box:
    label: str
    expected: str
    got: str
    verdict: str


@dataclass(frozen=True)
class Form:
    title: str
    filled: bool
    boxes: tuple[Box, ...]

    def count(self, verdict: str) -> int:
        return sum(b.verdict == verdict for b in self.boxes)


@dataclass(frozen=True)
class ScriptRun:
    script: str
    title: str
    mode: str  # typed or voice: typed when what the app heard is the script itself
    forms: tuple[Form, ...]

    @property
    def right(self) -> int:
        return sum(f.count(RIGHT) for f in self.forms)

    @property
    def scored(self) -> int:
        return self.right + sum(f.count(WRONG) for f in self.forms)


@dataclass(frozen=True)
class Run:
    folder: str
    started: datetime
    scripts: tuple[ScriptRun, ...]


def _unescape(cell: str) -> str:
    return cell.replace("\\|", "|").strip()


def parse_results(text: str, folder: str) -> Run | None:
    """One RESULTS.md → a Run. Unknown lines are skipped; a file without the title line is not a run."""
    started = None
    scripts: list[ScriptRun] = []
    script: tuple[str, str] | None = None
    forms: list[Form] | None = None
    boxes: list[Box] = []
    form_title, form_filled, script_text, heard = "", True, "", ""
    quote_of = ""

    def close_form():
        if form_title and forms is not None:
            forms.append(Form(form_title, form_filled, tuple(boxes)))

    def close_script():
        close_form()
        if script is not None:
            mode = TYPED if " ".join(heard.split()) == " ".join(script_text.split()) else VOICE
            scripts.append(ScriptRun(script[0], script[1], mode, tuple(forms)))

    for line in text.splitlines():
        if m := RUN_TITLE.match(line):
            started = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        elif m := SCRIPT_TITLE.match(line):
            close_script()
            script, forms, boxes, form_title, script_text, heard = (m.group(1), m.group(2)), [], [], "", "", ""
        elif line.startswith("**The script:**"):
            quote_of = "script"
        elif line.startswith("**What the app heard:**"):
            quote_of = "heard"
        elif line.startswith("> "):
            if quote_of == "script":
                script_text += line[2:]
            elif quote_of == "heard":
                heard += line[2:]
        elif m := FORM_TITLE.match(line):
            close_form()
            form_title, form_filled, boxes = m.group(1), m.group(2) is not None, []
        elif (m := BOX_ROW.match(line)) and boxes is not None:
            boxes.append(Box(_unescape(m.group(2)), _unescape(m.group(3)), _unescape(m.group(4)), m.group(1)))
    close_script()
    if started is None:
        return None
    return Run(folder, started, tuple(scripts))


def load_runs(results_dir: Path = RESULTS_DIR) -> list[Run]:
    """Every run that has a RESULTS.md, oldest first."""
    runs = []
    for path in sorted(Path(results_dir).glob("*/RESULTS.md")):
        run = parse_results(path.read_text(encoding="utf-8"), path.parent.name)
        if run is not None:
            runs.append(run)
    return sorted(runs, key=lambda r: r.started)


# ---------- the reports filed (records/<date>_<name>/) ----------

@dataclass(frozen=True)
class ReportForm:
    form: str
    title: str
    filled: int
    to_check: int  # boxes with a note + boxes to fill by hand
    print_pdf: str  # file name inside the record folder, "" if the file is gone
    editable_pdf: str


@dataclass(frozen=True)
class Report:
    id: str
    created: str  # "YYYY-MM-DD HH:MM"
    source: str
    story: str  # the first words of what was said
    forms: tuple[ReportForm, ...]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_reports(records_dir: Path = RECORDS_DIR) -> list[Report]:
    """Every saved report that has a record.json, newest first. A folder that can't be read is skipped."""
    titles = {f.id: f.title for f in load_forms()}
    reports = []
    for folder in sorted(Path(records_dir).glob("*/")):
        record = _read_json(folder / "record.json")
        if not isinstance(record, dict) or not record.get("created"):
            continue
        forms = []
        for entry in _read_json(folder / "forms.json") or []:
            if not isinstance(entry, dict) or not entry.get("form"):
                continue
            printed, editable = str(entry.get("print_pdf", "")), str(entry.get("editable_pdf", ""))
            forms.append(ReportForm(
                str(entry["form"]), titles.get(str(entry["form"]), str(entry["form"])), int(entry.get("filled", 0)),
                len(entry.get("notes") or []) + len(entry.get("by_hand") or []),
                printed if printed and (folder / printed).is_file() else "",
                editable if editable and (folder / editable).is_file() else ""))
        try:
            story = " ".join((folder / "transcript.txt").read_text(encoding="utf-8").split())
        except OSError:
            story = ""
        created = str(record["created"]).replace("T", " ")[:16]
        reports.append(Report(folder.name, created, str(record.get("source", "")), story[:STORY_CHARS], tuple(forms)))
    return sorted(reports, key=lambda r: r.created, reverse=True)


# ---------- the page ----------

def _data(runs: list[Run], reports: list[Report]) -> dict:
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records_dir": str(Path(RECORDS_DIR).resolve()),
        "forms": [{"id": f.id, "title": f.title, "say": list(f.say), "status": f.status} for f in load_forms()],
        "reports": [
            {"id": r.id, "created": r.created, "source": r.source, "story": r.story,
             "forms": [{"form": f.form, "title": f.title, "filled": f.filled, "to_check": f.to_check,
                        "print_pdf": f.print_pdf, "editable_pdf": f.editable_pdf} for f in r.forms]}
            for r in reports],
        "runs": [
            {
                "folder": r.folder,
                "started": r.started.strftime("%Y-%m-%d %H:%M"),
                "scripts": [
                    {
                        "script": s.script, "title": s.title, "mode": s.mode,
                        "right": s.right, "scored": s.scored,
                        "forms": [
                            {"title": f.title, "filled": f.filled, "right": f.count(RIGHT), "wrong": f.count(WRONG),
                             "look": f.count(LOOK),
                             "boxes": [{"label": b.label, "expected": b.expected, "got": b.got, "verdict": b.verdict}
                                       for b in f.boxes]}
                            for f in s.forms],
                    }
                    for s in r.scripts],
            }
            for r in runs],
    }


def render(runs: list[Run], reports: list[Report], token: str = "") -> str:
    """The page. Charts are drawn by the page's own script from the data embedded in it — no internet.
    `token` (set by the dashboard server) turns the run buttons on; the plain file has none."""
    payload = json.dumps(_data(runs, reports), ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__DATA__", payload).replace("__TOKEN__", token)


def write_dashboard(out: Path = DASHBOARD, results_dir: Path = RESULTS_DIR,
                    records_dir: Path = RECORDS_DIR) -> tuple[Path, int, int]:
    """Write the page. Returns (path, live-test runs, reports). The old address gets a page that jumps to the new one."""
    runs, reports = load_runs(results_dir), load_reports(records_dir)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(runs, reports), encoding="utf-8")
    out.chmod(0o600)
    if out == DASHBOARD and OLD_DASHBOARD.parent.is_dir():
        OLD_DASHBOARD.write_text(REDIRECT.replace("__URL__", out.resolve().as_uri()), encoding="utf-8")
        OLD_DASHBOARD.chmod(0o600)
    return out, len(runs), len(reports)
