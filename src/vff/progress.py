"""Where the app is in a run — one small file the dashboard reads to draw its progress bar.

record, make-report and live-test write data_tracker/progress.json at each step: the step, a line to show, how far
along it is, and at the end the report folder and its PDFs, so the page can open the filled form by itself.
Progress never fails a run: a problem writing the file is ignored.
"""

import json
import os
import time
from pathlib import Path

from vff.paths import DATA_TRACKER_DIR
from vff.storage import FILE_MODE, private_folder

PROGRESS_FILE = DATA_TRACKER_DIR / "progress.json"
STEPS = {  # per kind of run, in order: (step, label shown on the page)
    "report": (("ask", "Which form"), ("listen", "Listening"), ("heard", "Heard"), ("facts", "Finding facts"),
               ("fill", "Filling"), ("save", "Saving"), ("done", "Done")),
    "file": (("heard", "Reading the file"), ("facts", "Finding facts"), ("fill", "Filling"), ("save", "Saving"),
             ("done", "Done")),
    "test": (("listen", "Reading"), ("heard", "Heard"), ("facts", "Finding facts"), ("fill", "Filling"),
             ("save", "Checking"), ("done", "Done")),
}
STOPPED = "stopped"


def _read_file(path: Path = PROGRESS_FILE) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _write(state: dict, path: Path = PROGRESS_FILE) -> None:
    try:
        private_folder(path.parent)
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except OSError:
        pass


def percent(steps: list, step: str, part: tuple[int, int] | None) -> int:
    """How far along: the step's place in the list, plus `part` = (done, of) inside that step."""
    names = [s[0] for s in steps]
    if step not in names or len(names) < 2:
        return 100 if step == "done" else 0
    span = 1 / (len(names) - 1)
    within = span * part[0] / part[1] if part and part[1] else 0
    return round(100 * min(1.0, names.index(step) * span + within))


def begin(kind: str, message: str) -> None:
    """A new run starts: `kind` picks the steps shown (report, file or test)."""
    steps = [list(s) for s in STEPS[kind]]
    _write({"kind": kind, "steps": steps, "step": steps[0][0], "message": message, "percent": 0, "pid": os.getpid(),
            "started": time.time(), "updated": time.time(), "report": "", "pdfs": [], "run": ""})


def _current() -> dict:
    """The run's state so far; a fresh one if the file is gone (deleted mid-run) so no field is ever missing."""
    state = _read_file()
    if "started" in state:
        return state
    return {"kind": "", "steps": [], "step": "", "message": "", "percent": 0, "pid": os.getpid(),
            "started": time.time(), "updated": time.time(), "report": "", "pdfs": [], "run": ""}


def step(name: str, message: str, part: tuple[int, int] | None = None) -> None:
    """The run reached `name`; `part` = (done, of) for a step with several pieces, e.g. form 2 of 3."""
    state = _current()
    _write({**state, "step": name, "message": message, "updated": time.time(),
            "percent": percent(state.get("steps", []), name, part)})


def writing(report: str = "", run: str = "") -> None:
    """The folder this run is filling — `report` in records/, `run` in live_test/results/. A run stopped from the
    dashboard before it finishes has that folder thrown away."""
    state = _current()
    _write({**state, "updated": time.time(), **({"report": report} if report else {}), **({"run": run} if run else {})})


def finish(message: str, report: str = "", pdfs: tuple[str, ...] = (), run: str = "") -> None:
    """The run is done. `report` = the records/ folder and `pdfs` its printed forms; `run` = a live-test folder."""
    state = _current()
    _write({**state, "step": "done", "message": message, "percent": 100, "updated": time.time(),
            "report": report, "pdfs": list(pdfs), "run": run})


def fail(message: str) -> None:
    state = _current()
    _write({**state, "step": STOPPED, "message": message, "updated": time.time()})


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # it exists but belongs to someone else
    return True


def read() -> dict:
    """The current state for the page, with `age` = seconds since the last update; {} when there is none.
    A run whose process is gone (window closed, Ctrl-C) is reported as stopped."""
    state = _read_file()
    if not state:
        return {}
    running = state.get("step") not in ("done", STOPPED)
    if running and state.get("pid") and not _alive(int(state["pid"])):
        state = {**state, "step": STOPPED, "message": "The run ended before it finished — see its output below"}
    return {**state, "age": round(time.time() - float(state.get("updated", 0)))}
