"""Tell what happened; the app does the rest. Everything stays on this Mac.

    uv run record

Press Enter or say "start recording", tell the story in your own words (start with who you are), then say
"stop recording". The app writes down what it heard, fills every safety form that applies, saves them in
records/<date>_incident/, adds the report to data_tracker/reports.xlsx, and opens the filled forms.
"""

import argparse
import sys

import ollama
import sounddevice as sd

from vff import transcriber
from vff.cli.make_report import file_report, missing_line
from vff.dashboard import write_dashboard
from vff.export_excel import rebuild_workbook
from vff.extract import DEFAULT_MODEL
from vff.incident import PROFILE_PATH, load_profile
from vff.paths import RECORDS_DIR
from vff.system import show, speak
from vff.triggers import parse_stop_phrases
from vff.voice import listen, start_on_enter_or_phrase

ORDER = """Say it in this order:
  0. Which form — "OSHA form", "South Dakota form" or "Mishap" (say none: every form that fits)
  1. Who you are — name, job title, phone
  2. Who got hurt — name, job, address, date of birth, date hired
  3. When — the date, when they started work, when it happened (a.m./p.m.)
  4. Where — the place, and if it was on the employer's premises
  5. What happened — what they were doing, what happened, the injury and body part (left/right)
  6. Treatment — clinic or hospital, doctor, ER yes/no, kept overnight yes/no
  7. Safety equipment, witness, who it was reported to and when
  8. Only if it applies — returned to work, date of death
  9. Military mishap only — ship, where (at sea / port, base), the space, kind of event, times, weather, sea,
     wind, eyewitnesses; for a preliminary report also the one-liner, the date reported to the safety office,
     and the ISB and SIB investigators"""  # README: "What to say"
PAUSE_SECONDS = 10.0  # thinking pauses are normal; only "stop recording" or this much silence ends the story


def _say(line: str) -> None:
    print(line, flush=True)


def _record(hints: str) -> str | None:
    stop = parse_stop_phrases("")[0]
    _say("\n" + ORDER)
    _say('\nPress Enter or say "start recording", then just tell what happened.')
    _say(f'Start with who you are. Say "{stop}" when you\'re done.\n')
    rest = start_on_enter_or_phrase(hints)
    speak("Go ahead.")
    _say(f'● Recording…  say "{stop}" when you\'re done')
    text = listen(PAUSE_SECONDS, hints, wait_seconds=30.0, phrases=parse_stop_phrases(""))
    return " ".join(part for part in (rest, text) if part) or None


def _check_line(result) -> str:
    to_check = len(result.filled.notes) + len(result.filled.by_hand)
    extra = f" — {to_check} box{'es' if to_check != 1 else ''} to check" if to_check else ""
    return f"✓ {result.form.title} filled{extra}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hints", default="", help="names or words to spell right, e.g. \"Marcus Hill, Greenville\"")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    _say("Voice Form Filler")
    try:
        profile = load_profile(PROFILE_PATH)
    except ValueError as err:
        print(f"Stopped: {err}", file=sys.stderr)
        return 2
    if not profile:
        _say(f"(No company details yet — employer boxes stay blank unless you say the company. Add them in {PROFILE_PATH}.)")
    transcriber.go_offline()
    try:
        heard = _record(args.hints)
        if not heard:
            _say("Nothing was heard. Nothing saved.")
            return 1
        _say(f"\nWhat I heard:\n  {heard}\n")
        _say("✓ Got it. Filling the forms… (about a minute)")
        folder, results = file_report(heard, "live recording", args.model, profile, RECORDS_DIR, verbose=False)
    except (ollama.ResponseError, ConnectionError) as err:
        print(f"The local AI isn't available ({err}). Start it with: brew services start ollama", file=sys.stderr)
        return 2
    except sd.PortAudioError as err:
        print(f"Couldn't use the microphone ({err}). Nothing saved.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        _say("\nStopped. Nothing saved.")
        return 130

    if not results:
        _say("No safety form fits this story (no one was hurt?). The story is saved in:\n  " + str(folder))
    for result in results:
        _say(_check_line(result))
        if result.filled.missing:
            _say(f"  ⚑ {missing_line(result.filled.missing)}")
    try:
        workbook, _ = rebuild_workbook(RECORDS_DIR)
        _say(f"✓ Added to {workbook.relative_to(workbook.parents[1])}")
        dashboard, _, _ = write_dashboard()
        _say(f"✓ Dashboard updated: {dashboard.relative_to(dashboard.parents[1])}")
    except (OSError, ValueError) as err:
        _say(f"⚠ The Excel file wasn't updated ({err}). The forms are saved; run `uv run add-old-pdfs` to catch up.")
    for result in results:
        show(result.print_pdf)  # the filled forms
    _say(f"\nDone. Saved in {folder.relative_to(RECORDS_DIR.parent)}/" + (" — the forms are open." if results else ""))
    speak("Done. Your forms are ready." if results else "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
