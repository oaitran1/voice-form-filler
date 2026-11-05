"""Serve the dashboard on this computer only (127.0.0.1), so its buttons can run the app with a click.

    GET  /                     the page, rebuilt from records/ and live_test/results/ on every load
    GET  /records/<r>/<f>.pdf  a filled PDF from records/
    GET  /progress             where the current run is (data_tracker/progress.json), for the progress bar
    GET  /output?since=N       what the running command has printed so far (line N onwards)
    POST /upload               saves a recording from the browser (a phone's voice memo) in data/uploads/
    POST /run/<button>         runs that button's command as a hidden process (the fixed list below) — nothing else
    POST /stop                 the kill switch: ends the run now and throws away what it had saved so far

record and live-test use the microphone and speak through the speakers like before; only their words come to the
page instead of a Terminal window. One command runs at a time. Every POST must carry the page's own one-time token,
so another web page in the browser can't press the buttons.
"""

import errno
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from vff import progress
from vff.dashboard import load_reports, load_runs, render
from vff.export_excel import WORKBOOK, rebuild_workbook
from vff.forms import load_forms
from vff.live_test import RESULTS_DIR, load_scripts
from vff.media import AUDIO_VIDEO_TYPES, TEXT_TYPES
from vff.paths import DATA_DIR, DATA_TRACKER_DIR, RECORDS_DIR, ROOT
from vff.records import delete_record
from vff.storage import FILE_MODE, private_folder
from vff.system import show

HOST, PORT = "127.0.0.1", 8631
PORT_TRIES = 10  # if the port is taken by another program, the next ones are tried
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")  # a record folder or PDF name; no slashes
KEEP_LINES = 400  # of a command's output, for the page
RUNS_LOG = DATA_TRACKER_DIR / "runs.log"  # everything every run printed, kept so a failed run can be read later
STOP_WAIT_SECONDS = 5
UPLOADS_DIR = DATA_DIR / "uploads"  # recordings sent from the browser (private, gitignored with data/)
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # a two-hour phone recording is well under this


def _record_command(choice: str, _file: str = "") -> list[str]:
    """`choice` = a form id, "any" for every form that fits, or "voice" to start when a form's name is said."""
    ids = {f.id for f in load_forms()}
    if choice not in ("any", "voice") and choice not in ids:
        raise ValueError(f"unknown form {choice!r}")
    return [sys.executable, "-m", "vff.cli.record", "--form", choice, "--no-open"]


def _memo_command(choice: str, file: str) -> list[str]:
    """A recording uploaded to data/uploads/ (`file` = its saved name) → the same report as a live one.
    `choice` = a form id or "any"."""
    ids = {f.id for f in load_forms()}
    if choice != "any" and choice not in ids:
        raise ValueError(f"unknown form {choice!r}")
    if not SAFE_NAME.match(file) or not (UPLOADS_DIR / file).is_file():
        raise ValueError("the recording wasn't uploaded — pick the file again")
    command = [sys.executable, "-m", "vff.cli.make_report", "--input", str(UPLOADS_DIR / file)]
    return command + (["--forms", choice] if choice != "any" else [])


def save_upload(name: str, data: bytes) -> str:
    """Keep a recording sent from the browser as data/uploads/<time>_<name> (owner-only). Returns the saved name."""
    suffix = Path(name).suffix.lower()
    if suffix not in TEXT_TYPES | AUDIO_VIDEO_TYPES:
        raise ValueError(f"{suffix or 'that'} isn't a recording or text file the app can read")
    plain = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(name).stem).strip("._-")[:60] or "recording"
    saved = f"{datetime.now():%Y-%m-%d_%H%M%S}_{plain}{suffix}"
    private_folder(UPLOADS_DIR)
    fd = os.open(UPLOADS_DIR / saved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
    return saved


def _test_command(choice: str, typed: bool, _file: str = "") -> list[str]:
    """`choice` = a script number, or "all"."""
    command = [sys.executable, "-m", "vff.cli.live_test", "--no-open"] + (["--typed"] if typed else [])
    if choice != "all":
        if not (choice.isdigit() and 1 <= int(choice) <= len(load_scripts())):
            raise ValueError(f"unknown script {choice!r}")
        command += ["--script", choice]
    elif not typed:
        raise ValueError("a spoken test is one script at a time — pick one")
    return command


@dataclass(frozen=True)
class Button:
    title: str
    command: Callable[[str, str], list[str]] | None = None  # (choice, uploaded file) -> argv run in the background
    opens: Path | None = None  # a file or folder to open instead
    message: str = ""  # shown on the page after the click


BUTTONS = {
    "record": Button("Record a report", _record_command, message="Listening — tell what happened. Say \"stop recording\" when you're done."),
    "memo": Button("Recording from a file", _memo_command, message="Reading the recording — this page follows along."),
    "live-test": Button("Spoken test", lambda c, f: _test_command(c, typed=False), message="Spoken test started — read the script out loud; its first words start the recording."),
    "typed-test": Button("Typed test", lambda c, f: _test_command(c, typed=True), message="Typed test running; this page follows along."),
    "excel": Button("Excel tracker", opens=WORKBOOK, message="Opening the Excel tracker."),
    "records": Button("Records folder", opens=RECORDS_DIR, message="Opening the records folder."),
}


@dataclass
class Run:
    """One command running in the background and what it has printed."""
    name: str
    title: str
    process: subprocess.Popen
    started: datetime
    lines: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def alive(self) -> bool:
        return self.process.poll() is None

    def _read(self) -> None:
        DATA_TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        with open(RUNS_LOG, "a", encoding="utf-8") as log:
            log.write(f"\n=== {self.started:%Y-%m-%d %H:%M:%S} {self.title} ===\n")
            for line in self.process.stdout:  # type: ignore[union-attr]
                log.write(line)
                with self.lock:
                    self.lines.append(line.rstrip("\n"))
                    del self.lines[:-KEEP_LINES]
        self.process.wait()

    def snapshot(self, since: int) -> dict:
        with self.lock:
            total = len(self.lines)
            lines = self.lines[max(0, since - (total - KEEP_LINES) if total > KEEP_LINES else since):] if since < total else []
        return {"name": self.name, "title": self.title, "running": self.alive, "exit": self.process.poll(),
                "started": self.started.strftime("%H:%M:%S"), "lines": lines, "total": total}

    def stop(self) -> None:
        """End the run and everything it started (the spoken prompts, ffmpeg): they share one process group."""
        if not self.alive:
            return
        _signal_group(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(STOP_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            _signal_group(self.process.pid, signal.SIGKILL)
            self.process.wait()


def _signal_group(pid: int, sig: int) -> None:
    """Send `sig` to the run's whole process group (Mac/Linux), or end the one process (Windows)."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(pid, sig)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # already gone


def _terminal_run_pid(state: dict) -> int:
    """The pid of a run started from a terminal (`uv run record`) that progress.json says is still going — only
    when that process really is this app, so a reused pid is never touched. 0 when there is none."""
    pid = int(state.get("pid") or 0)
    if not pid or state.get("step") in ("", "done", progress.STOPPED) or not hasattr(os, "killpg"):
        return 0
    try:
        command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return pid if str(ROOT) in command else 0


def discard(state: dict) -> str:
    """Throw away what a stopped run had saved so far — its records/ folder (and its line in the index, and the Excel
    row) or its live_test/results/ folder. Returns what went, or '' when nothing was saved yet."""
    if state.get("step") in ("", "done", progress.STOPPED):
        return ""
    report, run = str(state.get("report", "")), str(state.get("run", ""))
    if state.get("kind") == "test" and SAFE_NAME.match(run) and (RESULTS_DIR / run).is_dir():
        shutil.rmtree(RESULTS_DIR / run)
        return f"threw away live_test/results/{run}"
    if state.get("kind") in ("report", "file") and SAFE_NAME.match(report) and delete_record(RECORDS_DIR, report):
        try:
            rebuild_workbook(RECORDS_DIR)  # the Excel file matches the saved reports again
        except (OSError, ValueError) as err:
            print(f"  ⚠ the Excel file wasn't rebuilt ({err}); run `uv run add-old-pdfs` to catch up", flush=True)
        return f"threw away records/{report}"
    return ""


class Runner:
    """At most one command at a time."""

    def __init__(self) -> None:
        self.current: Run | None = None
        self.lock = threading.Lock()

    def start(self, name: str, choice: str, file: str = "") -> str:
        """Press `name` with `choice` (and, for a recording from a file, its uploaded name); returns the message."""
        button = BUTTONS[name]
        if button.opens is not None:
            if not button.opens.exists():
                raise FileNotFoundError(f"{button.opens.name} doesn't exist yet")
            show(button.opens)
            return button.message
        if button.command is None:
            raise ValueError("this button opens nothing and runs nothing")
        argv = button.command(choice, file)
        with self.lock:
            if self.current is not None and self.current.alive:
                raise RuntimeError(f"{self.current.title} is still running — stop it first")
            process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1,
                                       env={**os.environ, "PYTHONUNBUFFERED": "1"}, start_new_session=True)
            label = button.title if choice in ("any", "all") else f"{button.title} — {'by voice' if choice == 'voice' else choice}"
            label = f"{button.title} — {file}" if file else label
            self.current = Run(name, label, process, datetime.now())
            threading.Thread(target=self.current._read, daemon=True).start()
        return button.message

    def output(self, since: int) -> dict:
        return self.current.snapshot(since) if self.current else {"running": False, "lines": [], "total": 0}

    def stop(self) -> str:
        """The kill switch: end the run now — one started here, or from a terminal — and save nothing from it."""
        state = progress.read()
        run = self.current
        if run is not None and run.alive:
            run.stop()
            title = run.title
        elif (pid := _terminal_run_pid(state)):
            _signal_group(pid, signal.SIGTERM)
            title = "The run in the terminal"
        else:
            return "Nothing is running."
        gone = discard(state)
        progress.fail("Stopped — nothing saved" + (f" ({gone})" if gone else ""))
        return f"{title} stopped. Nothing saved" + (f" — {gone}." if gone else ".")


RUNNER = Runner()


def record_pdf(folder: str, name: str) -> Path | None:
    """The PDF `records/<folder>/<name>` if the names are plain and the file is there, else None."""
    if not (SAFE_NAME.match(folder) and SAFE_NAME.match(name) and name.endswith(".pdf")):
        return None
    path = (RECORDS_DIR / folder / name).resolve()
    return path if path.is_file() and RECORDS_DIR.resolve() in path.parents else None


class Handler(BaseHTTPRequestHandler):
    token = ""

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, **payload) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # the name http.server expects
        url = urlsplit(self.path)
        if url.path in ("/", "/index.html"):
            page = render(load_runs(), load_reports(), token=self.token)
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if url.path == "/progress":
            self._json(200, **progress.read())
            return
        if url.path == "/output":
            since = parse_qs(url.query).get("since", ["0"])[0]
            self._json(200, **RUNNER.output(int(since) if since.isdigit() else 0))
            return
        parts = url.path.split("/")
        pdf = record_pdf(parts[2], parts[3]) if len(parts) == 4 and parts[1] == "records" else None
        if pdf is None:
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, pdf.read_bytes(), "application/pdf")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    def do_POST(self) -> None:
        origin = self.headers.get("Origin", "")
        if self.headers.get("X-VFF-Token", "") != self.token or (origin and origin != f"http://{self.headers.get('Host', '')}"):
            self._json(403, ok=False, message="This page is out of date — reload it.")
            return
        path = urlsplit(self.path).path
        if path == "/stop":
            self._json(200, ok=True, message=RUNNER.stop())
            return
        if path == "/upload":
            self._upload()
            return
        name = path.removeprefix("/run/")
        if name not in BUTTONS:
            self._json(404, ok=False, message="Unknown button.")
            return
        body = self._body()
        choice, file = str(body.get("choice", "")).strip()[:40], str(body.get("file", "")).strip()[:120]
        try:
            self._json(200, ok=True, message=RUNNER.start(name, choice, file))
        except (OSError, ValueError, RuntimeError) as err:
            self._json(409 if isinstance(err, RuntimeError) else 500, ok=False, message=f"Couldn't do that: {err}")

    def _upload(self) -> None:
        """The request body is the recording; X-VFF-Name is its file name."""
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not 0 < length <= MAX_UPLOAD_BYTES:
            self._json(413, ok=False, message="That file is empty or too big (the limit is 500 MB).")
            return
        try:
            saved = save_upload(self.headers.get("X-VFF-Name", ""), self.rfile.read(length))
        except (OSError, ValueError) as err:
            self._json(400, ok=False, message=f"Couldn't keep the recording: {err}")
            return
        self._json(200, ok=True, file=saved, message=f"Got {saved}.")

    def log_message(self, fmt, *args) -> None:  # one short line per click, silence for page loads
        if self.command == "POST":
            print(f"  {self.path.lstrip('/')} → {args[1]}", flush=True)


def _bind(port: int) -> ThreadingHTTPServer:
    """The server on `port`, or on the next free port after it when another program holds it."""
    for candidate in range(port, port + PORT_TRIES):
        try:
            return ThreadingHTTPServer((HOST, candidate), Handler)
        except OSError as err:
            if err.errno != errno.EADDRINUSE:
                raise
    raise OSError(f"ports {port}–{port + PORT_TRIES - 1} are all in use")


def _end(signum, frame) -> None:
    raise KeyboardInterrupt  # `uv run dashboard --stop` sends SIGTERM: leave the same way as Ctrl-C


def serve(port: int = PORT, open_page: bool = True) -> None:
    """Run until Ctrl-C or `uv run dashboard --stop`. The page's buttons work only while this runs."""
    Handler.token = secrets.token_hex(16)
    signal.signal(signal.SIGTERM, _end)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)  # the window it was started from may close; keep going
    server = _bind(port)
    url = f"http://{HOST}:{server.server_address[1]}/"
    print(f"Dashboard at {url} (this Mac only). Ctrl-C stops it.", flush=True)
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        RUNNER.stop()
        server.server_close()
