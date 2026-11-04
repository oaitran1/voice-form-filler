"""Serve the dashboard on this Mac only (127.0.0.1), so its buttons can start the app with a click.

    GET  /                     the page, rebuilt from records/ and live_test/results/ on every load
    GET  /records/<r>/<f>.pdf  a filled PDF from records/
    POST /run/<button>         runs that button's command (the fixed list below) — nothing else can be run

A button that needs the microphone or the keyboard (record, live-test) opens a new Terminal window, so you talk
there and see the output. Every POST must carry the page's own one-time token, so another web page in the browser
can't press the buttons.
"""

import errno
import json
import re
import secrets
import shlex
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from vff.dashboard import load_reports, load_runs, render
from vff.export_excel import WORKBOOK
from vff.paths import RECORDS_DIR, ROOT
from vff.system import show

HOST, PORT = "127.0.0.1", 8631
PORT_TRIES = 10  # if the port is taken by another program, the next ones are tried
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")  # a record folder or PDF name; no slashes, no leading dot


@dataclass(frozen=True)
class Button:
    terminal: str = ""  # a command to run in a new Terminal window, from the app folder
    opens: Path | None = None  # a file or folder to open instead
    message: str = ""  # shown on the page after the click


BUTTONS = {
    "record": Button("uv run record", message="A Terminal window opened — say what happened there."),
    "live-test": Button("uv run live-test", message="A Terminal window opened — pick a script and read it out loud there."),
    "typed-test": Button("uv run live-test --typed --no-open", message="Typed test running in a Terminal window; this page updates when it's done."),
    "excel": Button(opens=WORKBOOK, message="Opening the Excel tracker."),
    "records": Button(opens=RECORDS_DIR, message="Opening the records folder."),
}


def _applescript_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def open_terminal(command: str) -> None:
    """Run `command` in a new Terminal window, from the app folder (Mac only)."""
    if sys.platform != "darwin":
        raise OSError("the buttons open a Terminal window, which only works on a Mac")
    line = _applescript_text(f"cd {shlex.quote(str(ROOT))} && {command}")
    script = f'tell application "Terminal"\nactivate\ndo script "{line}"\nend tell'
    done = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if done.returncode != 0:
        raise OSError(done.stderr.strip() or "Terminal could not be opened")


def press(name: str) -> str:
    """Do what the button `name` does; returns the message for the page."""
    button = BUTTONS[name]
    if button.opens is not None:
        if not button.opens.exists():
            raise FileNotFoundError(f"{button.opens.name} doesn't exist yet")
        show(button.opens)
    else:
        open_terminal(button.terminal)
    return button.message


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
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            page = render(load_runs(), load_reports(), token=self.token)
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        parts = path.split("/")
        pdf = record_pdf(parts[2], parts[3]) if len(parts) == 4 and parts[1] == "records" else None
        if pdf is None:
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, pdf.read_bytes(), "application/pdf")

    def do_POST(self) -> None:
        origin = self.headers.get("Origin", "")
        if self.headers.get("X-VFF-Token", "") != self.token or (origin and origin != f"http://{self.headers.get('Host', '')}"):
            self._json(403, ok=False, message="This page is out of date — reload it.")
            return
        name = urlsplit(self.path).path.removeprefix("/run/")
        if name not in BUTTONS:
            self._json(404, ok=False, message="Unknown button.")
            return
        try:
            self._json(200, ok=True, message=press(name))
        except OSError as err:
            self._json(500, ok=False, message=f"Couldn't do that: {err}")

    def log_message(self, fmt, *args) -> None:  # one short line per click, silence for page loads
        if self.command == "POST":
            print(f"  button {self.path.removeprefix('/run/')} → {args[1]}", flush=True)


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
        server.server_close()
