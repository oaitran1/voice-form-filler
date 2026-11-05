"""Tell what happened; the app does the rest. Everything stays on this computer.

    uv run record
    uv run record --form osha_301      # skip the first question

It first asks which form you are filling out — say "OSHA form 301" or "Mishap" (or "any" for every form that
fits, or type its number). Naming the form starts the recording: it says "Go ahead", you tell the
story in your own words (start with who you are) and say "stop recording". The app writes down what it heard, fills
the form(s), saves them in records/<date>_incident/, adds the report to data_tracker/reports.xlsx, and opens them.
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
from vff.forms import FormMap, forms_said, load_forms, opens_story
from vff.incident import PROFILE_PATH, load_profile
from vff import progress
from vff.paths import RECORDS_DIR
from vff.system import show, speak
from vff.triggers import parse_stop_phrases
from vff.voice import listen, wait_for_start

ORDER = """Say it in this order:
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
ANY_FORM = ("any", "all", "every", "everything", "whatever")  # answers that mean "every form that fits"
VOICE = "voice"  # --form voice: no question — the recording starts when a form's name (or a report's opening) is heard
ANSWER_SECONDS = 8.0  # how long the first question waits for a spoken answer before asking you to type


def _say(line: str) -> None:
    print(line, flush=True)


def _form_from_answer(answer: str, forms: list[FormMap]) -> list[FormMap] | None:
    """The form(s) an answer names: a say-word, a number from the list, or a word meaning 'any' ([]).
    None = not understood."""
    words = answer.lower().split()
    if any(w.strip(".,!") in ANY_FORM for w in words) or answer.strip() == "0":
        return []
    if answer.strip().isdigit() and 1 <= int(answer.strip()) <= len(forms):
        return [forms[int(answer.strip()) - 1]]
    named = forms_said(answer, forms)
    return named or None


def choose_form(forms: list[FormMap], hear, read_line) -> list[FormMap]:
    """Ask which form is being filled out. `hear()` listens once (text or None); `read_line(prompt)` reads a typed
    answer. Returns the chosen form(s); [] means every form that fits the story."""
    menu = "\n".join(f"  {i}. {f.title} — say \"{f.say[0]}\"" for i, f in enumerate(forms, 1)) + "\n  0. Any — every form that fits"
    _say("\n" + ORDER)
    progress.step("ask", "Which form? Say its name — " + ", ".join(f'"{f.say[0]}"' for f in forms) + ' or "any"')
    _say("\nWhich form are we filling out? Say it (e.g. \"OSHA form 301\") — the recording starts right after.\n" + menu)
    speak("Which form are we filling out? " + ", ".join(f.say[0] for f in forms) + ", or any.")
    answer = hear()
    if answer:
        _say(f'  (heard "{answer}")')
        chosen = _form_from_answer(answer, forms)
        if chosen is not None:
            return chosen
        _say("  I didn't catch a form name in that.")
    while True:
        try:
            typed = read_line(f"Type the number (1-{len(forms)}, or 0 for any): ").strip()
        except EOFError:  # no keyboard (started from the dashboard): every form that fits
            _say("  No answer — every form that fits the story will be filled.")
            return []
        chosen = _form_from_answer(typed, forms)
        if chosen is not None:
            return chosen
        _say(f"  Please type a number from 0 to {len(forms)}.")


def wait_for_form(forms: list[FormMap], hints: str) -> tuple[list[FormMap], str]:
    """No question: wait until a form's name is said ("OSHA form 301", "Mishap") or a report begins ("This report is
    by…"), then that form is the one — and those words are the start of the story. Returns (forms, the words)."""
    names = ", ".join(f'"{f.say[0]}"' for f in forms)
    _say("\n" + ORDER)
    _say(f"\nListening. Say the form's name to start — {names} — then tell what happened.")
    progress.step("ask", f"Say the form's name to start — {names}")
    heard = wait_for_start(hints, on_heard=lambda text: _say(f'  (heard "{text}" — say a form\'s name to start)'),
                           starts_story=lambda text: opens_story(text, forms))
    return forms_said(heard, forms), heard


def _record(hints: str, chosen: list[FormMap], opening: str = "") -> str | None:
    """Recording starts right after the form is chosen — naming the form is the start cue. `opening` = words already
    heard that begin the story (voice start); they are kept."""
    stop = parse_stop_phrases("")[0]
    what = " and ".join(f.title for f in chosen) if chosen else "every form that fits the story"
    _say(f"\nOK — {what}. Go ahead" + (", carry on." if opening else ": start with who you are."))
    speak(f"OK, {what}. Go ahead.")
    _say(f'● Recording…  say "{stop}" when you\'re done')
    progress.step("listen", f'Listening — {what}. Tell what happened, then say "{stop}"')
    rest = listen(PAUSE_SECONDS, hints, wait_seconds=30.0, phrases=parse_stop_phrases(""))
    return " ".join(part for part in (opening, rest) if part) or None


def _check_line(result) -> str:
    to_check = len(result.filled.notes) + len(result.filled.by_hand)
    extra = f" — {to_check} box{'es' if to_check != 1 else ''} to check" if to_check else ""
    return f"✓ {result.form.title} filled{extra}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hints", default="", help="names or words to spell right, e.g. \"Marcus Hill, Greenville\"")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--form", default="", help="skip the first question: form id(s), e.g. osha_301 or osha_301,sd_froi; "
                        "any = every form that fits; voice = start when a form's name is said")
    parser.add_argument("--no-open", action="store_true", help="don't open the filled forms at the end (the dashboard shows them)")
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
    progress.begin("report", "Starting…")
    try:
        forms = sorted(load_forms(), key=lambda f: f.status != "approved")  # the everyday forms first, drafts last
        opening = ""
        if args.form.strip().lower() == VOICE:
            chosen, opening = wait_for_form(forms, args.hints)
        elif args.form.strip().lower() in ANY_FORM:
            chosen = []  # every form that fits the story
        elif args.form:
            ids = {w.strip() for w in args.form.split(",") if w.strip()}
            chosen = [f for f in forms if f.id in ids]
            if len(chosen) != len(ids):
                print(f"Stopped: unknown form in --form {args.form!r}. Forms: {', '.join(f.id for f in forms)}", file=sys.stderr)
                return 2
        else:
            chosen = choose_form(forms, lambda: listen(1.5, args.hints, wait_seconds=ANSWER_SECONDS), input)
        heard = _record(args.hints, chosen, opening)
        if not heard:
            progress.fail("Nothing was heard")
            _say("Nothing was heard. Nothing saved.")
            return 1
        _say(f"\nWhat I heard:\n  {heard}\n")
        _say("✓ Got it. Filling the forms… (about a minute)")
        progress.step("heard", "Got it — filling the forms (about a minute)")
        folder, results = file_report(heard, "live recording", args.model, profile, RECORDS_DIR, verbose=False,
                                      wanted_forms=",".join(f.id for f in chosen))
    except (ollama.ResponseError, ConnectionError) as err:
        progress.fail("The local AI isn't available")
        print(f"The local AI isn't available ({err}). Start it with: brew services start ollama", file=sys.stderr)
        return 2
    except sd.PortAudioError as err:
        progress.fail("Couldn't use the microphone")
        print(f"Couldn't use the microphone ({err}). Nothing saved.", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        progress.fail("Stopped")
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
    progress.finish(f"Done — {len(results)} form(s) filled" if results else "Done — no form fits this story",
                    report=folder.name, pdfs=tuple(r.print_pdf.name for r in results))
    if not args.no_open:
        for result in results:
            show(result.print_pdf)  # the filled forms
    _say(f"\nDone. Saved in {folder.relative_to(RECORDS_DIR.parent)}/" + (" — the forms are open." if results and not args.no_open else ""))
    speak("Done. Your forms are ready." if results else "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
