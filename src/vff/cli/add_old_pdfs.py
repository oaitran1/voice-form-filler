"""Bring old filled PDFs into the reports workbook (data_tracker/reports.xlsx). Offline.

    uv run add-old-pdfs ~/old_reports                 # a folder (searched inside) …
    uv run add-old-pdfs a.pdf b.pdf                   # … or single PDFs
    uv run add-old-pdfs                               # nothing new: just rebuild the workbook

The PDFs are COPIED into records/old_pdfs/ (your originals are not touched; a file already copied is skipped),
then data_tracker/reports.xlsx is rebuilt from every saved report — spoken and old — one sheet per form.
Forms it knows: the `excel:` part of templates/forms/*.yaml (OSHA 301, SD first report of injury).
PDFs it can't read or doesn't know go on the "Not exported" sheet, so nothing is lost.
"""

import argparse
import sys
from pathlib import Path

from vff.export_excel import PROBLEM_SHEET, add_old_pdfs, rebuild_workbook


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", help="old filled PDFs, or folders of them")
    args = parser.parse_args()
    try:
        if args.inputs:
            added, skipped = add_old_pdfs([Path(p).expanduser() for p in args.inputs])
            print(f"Copied {len(added)} PDF(s) into records/old_pdfs/"
                  + (f" ({len(skipped)} already there, skipped)" if skipped else "") + ".")
        out, summary = rebuild_workbook()
    except FileNotFoundError as err:
        print(f"Stopped: {err}", file=sys.stderr)
        return 2
    except ValueError as err:  # a broken templates/forms/*.yaml
        print(f"Stopped: {err}", file=sys.stderr)
        return 2
    except OSError as err:
        print(f"Couldn't write the workbook ({err}). Nothing in records/ was lost.", file=sys.stderr)
        return 2
    print(f"Workbook updated: {out}")
    for sheet, rows in summary.items():
        print(f"  {sheet}: {rows} {'file(s) to check by hand' if sheet == PROBLEM_SHEET else 'report(s)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
