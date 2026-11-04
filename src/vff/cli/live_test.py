"""Live test: read a script out loud, the app records you and fills the forms, then checks every box. Offline.

    uv run live-test               # asks which script: 1, 2, 3 … or Enter for all
                                   # then: press Enter OR say "start recording" → read → say "stop recording"
    uv run live-test --script 2    # only script 2 (no question)
    uv run live-test --typed       # no microphone: the script's words go straight in (checks the forms, not your voice)

Scripts and their right answers: live_test/scripts/*.yaml. The Excel file goes to data_tracker/live_test.xlsx
(the latest run). Each run also makes a new folder, then opens it:
    live_test/results/<date_time>/
        <script>/osha_301_filled.pdf, sd_froi_filled.pdf, transcript.txt …   ← the filled forms
        RESULTS.md                                                            ← every box: ✓ right, ✗ wrong, 👁 read it
The company details come from templates/examples/company_profile.yaml, so the right answers are always known.
"""

import argparse
import sys
from datetime import datetime

import ollama
import sounddevice as sd

from vff import transcriber
from vff.cli.make_report import file_report
from vff.export_excel import rebuild_workbook
from vff.extract import DEFAULT_MODEL
from vff.incident import load_profile
from vff.dashboard import write_dashboard
from vff.live_test import RESULTS_DIR, TEST_PROFILE, TEST_WORKBOOK, check_report, load_scripts, write_results
from vff.system import show, speak
from vff.storage import private_folder
from vff.triggers import parse_stop_phrases
from vff.voice import listen, start_on_enter_or_phrase

SILENCE_SECONDS = 3.0


def _choose(scripts: list) -> list:
    """Ask which script to read; Enter = all of them."""
    print("\nScripts:")
    for number, script in enumerate(scripts, start=1):
        print(f"  {number}  {script.title}")
    while True:
        answer = input(f"Which one? Type 1-{len(scripts)}, or just press Enter for all: ").strip()
        if not answer:
            return scripts
        if answer.isdigit() and 1 <= int(answer) <= len(scripts):
            return [scripts[int(answer) - 1]]
        print(f"  Please type a number from 1 to {len(scripts)}, or press Enter.")


def _show(number: int, total: int, script) -> None:
    print(f"\n{'=' * 78}\nREAD THIS — script {script.id[:2]} ({number} of {total}): {script.title}\n{'=' * 78}\n")
    print(script.text)
    print(f"\n{'=' * 78}")


def _record(script, number: int) -> str | None:
    """Start on Enter OR on saying "start recording"; stop on "stop recording"."""
    phrases = parse_stop_phrases("")
    print(f'\nWhen you are ready, press Enter or say "start recording". Wait for "Go ahead", then read the script'
          f' above.\nSay "{phrases[0]}" when you are done.')
    rest = start_on_enter_or_phrase(
        script.hints, on_heard=lambda heard: print(f'  (heard "{heard}" — press Enter or say "start recording")'))
    speak("Go ahead.")
    print("Recording…")
    text = listen(SILENCE_SECONDS, script.hints, phrases=phrases)
    return " ".join(part for part in (rest, text) if part) or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=int, help="run only this script number (1, 2, 3 …)")
    parser.add_argument("--typed", action="store_true", help="skip the microphone: use the script's words as heard")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--no-open", action="store_true", help="don't open the results folder at the end")
    args = parser.parse_args()

    try:
        scripts = load_scripts()
        if args.script:
            if not 1 <= args.script <= len(scripts):
                raise ValueError(f"There are {len(scripts)} scripts; pick 1 to {len(scripts)}.")
            scripts = [scripts[args.script - 1]]
        elif not args.typed and sys.stdin.isatty():
            scripts = _choose(scripts)
        profile = load_profile(TEST_PROFILE)
    except (FileNotFoundError, ValueError) as err:
        print(f"Stopped: {err}", file=sys.stderr)
        return 2

    started = datetime.now()
    run_dir = private_folder(RESULTS_DIR / f"{started:%Y-%m-%d_%H%M%S}")
    transcriber.go_offline()
    rows = []
    try:
        for number, script in enumerate(scripts, start=1):
            _show(number, len(scripts), script)
            heard = script.text if args.typed else _record(script, number)
            if not heard:
                print("Nothing was heard — skipping this script.")
                rows.append((script, "", None, []))
                continue
            print(f"\n--- What the app heard ---\n{heard}\n")
            source = "typed script" if args.typed else "live recording"
            folder, _ = file_report(heard, source, args.model, profile, run_dir, name=script.id)
            rows.append((script, heard, folder, check_report(script, folder, profile, f"{datetime.now():%m/%d/%Y}")))
    except (ollama.ResponseError, ConnectionError) as err:
        print(f"The local AI isn't available ({err}). Start it with: brew services start ollama", file=sys.stderr)
        return 2
    except sd.PortAudioError as err:
        print(f"Couldn't use the microphone ({err}).", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped. What was done so far is kept below.")

    workbook, _ = rebuild_workbook(run_dir, out=TEST_WORKBOOK)
    results, right, wrong, look = write_results(run_dir, rows, started)
    print(f"\n{'=' * 78}\nLIVE TEST: {right} of {right + wrong} boxes right, {wrong} wrong, {look} to read yourself.")
    print(f"Results: {results}\nExcel:   {workbook}")
    try:
        dashboard, _, _ = write_dashboard()
        print(f"Dashboard: {dashboard} (updated; an open page reloads by itself)")
    except OSError as err:
        print(f"⚠ The dashboard wasn't updated ({err}); run `uv run dashboard`.")
    print("=" * 78)
    speak(f"Done. {right} of {right + wrong} boxes right.")
    if not args.no_open:
        show(run_dir)  # the results folder
    return 0


if __name__ == "__main__":
    sys.exit(main())
