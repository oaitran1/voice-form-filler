"""The app's dashboard — reports filed, the forms, how accurate the live tests are, and buttons that run the app.

    uv run dashboard            # serves the page on this Mac only and opens it; the buttons work; Ctrl-C stops it
    uv run dashboard --write    # only writes data_tracker/dashboard.html (no buttons) and opens it
    uv run dashboard --no-open

Every `uv run record`, `make-report` and `live-test` rewrites the file too, and an open page reloads itself every 30 s.
"""

import argparse
import sys

from vff.dashboard import write_dashboard
from vff.dashboard_server import PORT, serve
from vff.system import show


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="write the HTML file instead of serving the page")
    parser.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    try:
        if args.write:
            out, runs, reports = write_dashboard()
            print(f"{reports} report(s), {runs} live test(s) → {out}")
            if not args.no_open:
                show(out)
        else:
            serve(args.port, open_page=not args.no_open)
    except OSError as err:
        print(f"Stopped: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
