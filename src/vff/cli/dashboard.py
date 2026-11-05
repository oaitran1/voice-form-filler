"""The app's dashboard — reports filed, the forms, how accurate the live tests are, and buttons that run the app.

    uv run dashboard            # starts the server in the background and opens the page; the window can be closed
    uv run dashboard --stop     # stops it
    uv run dashboard --here     # runs it in this window instead (Ctrl-C stops it)
    uv run dashboard --write    # only writes data_tracker/dashboard.html (no buttons) and opens it
    uv run dashboard --no-open

The page is served on this computer only. Started from a terminal, the background server keeps that terminal's
microphone permission, so recording from the page works. What it prints goes to data_tracker/server.log.
Every `uv run record`, `make-report` and `live-test` rewrites the HTML file too.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from vff.dashboard import write_dashboard
from vff.dashboard_server import HOST, PORT, PORT_TRIES, serve
from vff.paths import DATA_TRACKER_DIR, ROOT
from vff.storage import private_folder
from vff.system import show

PID_FILE = DATA_TRACKER_DIR / "dashboard.pid"
SERVER_LOG = DATA_TRACKER_DIR / "server.log"
START_WAIT_SECONDS = 20
STOP_WAIT_SECONDS = 5
PAGE_MARK = b"<title>Voice Form Filler</title>"  # only our page has this, so another program's page on the port isn't mistaken for it


def running_at(port: int) -> str:
    """The URL of our server if one answers on `port` or the next few, else ''."""
    for candidate in range(port, port + PORT_TRIES):
        url = f"http://{HOST}:{candidate}/"
        try:
            with urllib.request.urlopen(url, timeout=1) as reply:
                if PAGE_MARK in reply.read():
                    return url
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return ""


def start_in_background(port: int) -> str:
    """Start the server as its own process, wait until it answers, and return its URL ('' if it never did)."""
    private_folder(DATA_TRACKER_DIR)
    with open(SERVER_LOG, "a", encoding="utf-8") as log:
        child = subprocess.Popen([sys.executable, "-m", "vff.cli.dashboard", "--here", "--no-open", "--port", str(port)],
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)  # not tied to this window: closing it changes nothing
    PID_FILE.write_text(str(child.pid))
    for _ in range(START_WAIT_SECONDS * 2):
        if child.poll() is not None:
            return ""
        if url := running_at(port):
            return url
        time.sleep(0.5)
    return ""


def stop_background() -> str:
    """Stop the background server started here. Returns a line saying what happened."""
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return "The dashboard isn't running (nothing to stop)."
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return "The dashboard wasn't running any more."
    for _ in range(STOP_WAIT_SECONDS * 4):
        time.sleep(0.25)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
    PID_FILE.unlink(missing_ok=True)
    return "Dashboard stopped."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="write the HTML file instead of serving the page")
    parser.add_argument("--here", action="store_true", help="serve in this window (Ctrl-C stops it) instead of in the background")
    parser.add_argument("--stop", action="store_true", help="stop the background server")
    parser.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    try:
        if args.stop:
            print(stop_background())
        elif args.write:
            out, runs, reports = write_dashboard()
            print(f"{reports} report(s), {runs} live test(s) → {out}")
            if not args.no_open:
                show(out)
        elif args.here:
            serve(args.port, open_page=not args.no_open)
        else:
            url = running_at(args.port) or start_in_background(args.port)
            if not url:
                print(f"The dashboard didn't start — see {SERVER_LOG}", file=sys.stderr)
                return 2
            print(f"Dashboard on at {url} — it keeps running after this window is closed.\nStop it with: uv run dashboard --stop")
            if not args.no_open:
                webbrowser.open(url)
    except OSError as err:
        print(f"Stopped: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
