"""Serve the dashboard on this Mac only (127.0.0.1), so its buttons can run the app with a click — no Terminal window.

    GET  /                     the page, rebuilt from records/ and live_test/results/ on every load
    GET  /records/<r>/<f>.pdf  a filled PDF from records/
    GET  /progress             where the current run is (data_tracker/progress.json), for the progress bar
    GET  /output?since=N       what the running command has printed so far (line N onwards)
    POST /run/<button>         runs that button's command as a hidden process (the fixed list below) — nothing else
    POST /stop                 stops the running command

record and live-test use the microphone and speak through the speakers like before; only their words come to the
page instead of a Terminal window. One command runs at a time. Every POST must carry the page's own one-time token,
so another web page in the browser can't press the buttons.
"""

import errno
import json
import os
import re
import secrets
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
from vff.export_excel import WORKBOOK
from vff.forms import load_forms
from vff.live_test import load_scripts
from vff.paths import DATA_TRACKER_DIR, RECORDS_DIR, ROOT
from vff.system import show

HOST, PORT = "127.0.0.1", 8631
PORT_TRIES = 10  # if the port is taken by another program, the next ones are tried
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")  # a record folder or PDF name; no slashes
KEEP_LINES = 400  # of a command's output, for the page
RUNS_LOG = DATA_TRACKER_DIR / "runs.log"  # everything every run printed, kept so a failed run can be read later
STOP_WAIT_SECONDS = 5


def _record_command(choice: str) -> list[str]:
    """`choice` = a form id, "any" for every form that fits, or "voice" to start when a form's name is said."""
    ids = {f.id for f in load_forms()}
    if choice not in ("any", "voice") and choice not in ids:
        raise ValueError(f"unknown form {choice!r}")
    return [sys.executable, "-m", "vff.cli.record", "--form", choice, "--no-open"]


def _test_command(choice: str, typed: bool) -> list[str]:
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
    command: Callable[[str], list[str]] | None = None  # choice -> argv for a command run in the background
    opens: Path | None = None  # a file or folder to open instead
    message: str = ""  # shown on the page after the click


BUTTONS = {
    "record": Button("Record a report", _record_command, message="Listening — tell what happened. Say \"stop recording\" when you're done."),
    "live-test": Button("Spoken test", lambda c: _test_command(c, typed=False), message="Spoken test started — read the script out loud; its first words start the recording."),
    "typed-test": Button("Typed test", lambda c: _test_command(c, typed=True), message="Typed test running; this page follows along."),
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
        if self.alive:
            self.process.terminate()
            try:
                self.process.wait(STOP_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()


class Runner:
    """At most one command at a time."""

    def __init__(self) -> None:
        self.current: Run | None = None
        self.lock = threading.Lock()

    def start(self, name: str, choice: str) -> str:
        """Press `name` with `choice`; returns the message for the page."""
        button = BUTTONS[name]
        if button.opens is not None:
            if not button.opens.exists():
                raise FileNotFoundError(f"{button.opens.name} doesn't exist yet")
            show(button.opens)
            return button.message
        if button.command is None:
            raise ValueError("this button opens nothing and runs nothing")
        argv = button.command(choice)
        with self.lock:
            if self.current is not None and self.current.alive:
                raise RuntimeError(f"{self.current.title} is still running — stop it first")
            process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1,
                                       env={**os.environ, "PYTHONUNBUFFERED": "1"})
            label = button.title if choice in ("any", "all") else f"{button.title} — {'by voice' if choice == 'voice' else choice}"
            self.current = Run(name, label, process, datetime.now())
            threading.Thread(target=self.current._read, daemon=True).start()
        return button.message

    def output(self, since: int) -> dict:
        return self.current.snapshot(since) if self.current else {"running": False, "lines": [], "total": 0}

    def stop(self) -> str:
        run = self.current
        if run is None or not run.alive:
            return "Nothing is running."
        run.stop()
        progress.fail("Stopped from the dashboard")
        return f"{run.title} stopped."


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
        name = path.removeprefix("/run/")
        if name not in BUTTONS:
            self._json(404, ok=False, message="Unknown button.")
            return
        choice = str(self._body().get("choice", "")).strip()[:40]
        try:
            self._json(200, ok=True, message=RUNNER.start(name, choice))
        except (OSError, ValueError, RuntimeError) as err:
            self._json(409 if isinstance(err, RuntimeError) else 500, ok=False, message=f"Couldn't do that: {err}")

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


def serve(port: int = PORT, open_page: bool = True) -> None:
    """Run until Ctrl-C. The page's buttons work only while this runs."""
    Handler.token = secrets.token_hex(16)
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
