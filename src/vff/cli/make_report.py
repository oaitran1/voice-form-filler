"""Recording → filled safety forms → saved → a row in the reports workbook. Everything runs offline on this Mac.

ONE STORY → EVERY SAFETY FORM THAT APPLIES:
    uv run make-report --input ~/Downloads/incident.m4a                           # voice memo
    uv run make-report --live                                                     # talk now
    uv run make-report --input bodycam.mp4                                        # video (sound only)
    uv run make-report --input notes.txt                                          # typed notes
    uv run make-report --input memo.m4a --forms osha_301,sd_froi                  # only these forms
    uv run make-report --list                                                     # the forms it fills
    uv run make-report --brief                                                    # what to say + the forms
Company facts (employer, address, tax ID) come from data/profile.yaml (--profile), typed once — unless the story
says a company name; then the company details said in the story are used instead.

FIRST TIME ON A NEW MAC (the only steps that use internet):
    uv run make-report --setup                                                    # download the Whisper model
    ollama pull gemma3:12b                                                        # the local AI

Tell the story once; the forms are filled straight from it. Answers not backed by your words are left blank.
Each report is saved in records/<date>_incident/, then data_tracker/reports.xlsx is rebuilt (one row per report).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import ollama
import sounddevice as sd

from vff import transcriber
from vff.dashboard import write_dashboard
from vff.export_excel import rebuild_workbook
from vff.extract import DEFAULT_MODEL
from vff.forms import applies, forms_said, load_forms, needed_groups
from vff.incident import (PROFILE_PATH, build_record, fact_values, fill_forms, load_profile, spoken_templates,
                          story_template)
from vff.media import transcript_from_file
from vff.paths import RECORDS_DIR
from vff.system import speak
from vff.records import save_record
from vff.storage import write_new_private_file
from vff.templates import briefing
from vff.triggers import parse_stop_phrases
from vff.voice import listen

MARKS = {"ok": "✓", "check": "⚠", "unsupported": "✗"}


def get_transcript(args, template) -> tuple[str, str]:
    """Returns (transcript, source description)."""
    if args.live:
        phrases = parse_stop_phrases(args.stop_words)
        transcriber.go_offline()
        intro = briefing(template)
        print(f"\n{intro}\n")
        speak(intro)
        speak(f"Go ahead, I'm listening. Say {phrases[0]} when you're done.")
        text = listen(args.silence, args.hints, phrases=phrases)
        if not text:
            raise ValueError("Nothing was heard.")
        return text, "live recording"
    path = Path(args.input).expanduser()
    return transcript_from_file(path, hints=args.hints), f"file: {path.name}"


def print_answers(template, answers: dict[str, dict]) -> None:
    print(f"\n=== {template.title} ===")
    for field in template.fields:
        a = answers[field.key]
        if a["value"]:
            print(f"{MARKS[a['check']]} {field.label}: {a['value']}")
            if a["check"] == "check":
                print(f"     ⚠ {a['note']}")
        elif a["note"]:
            print(f"✗ {field.label}: (blank) — {a['note']}")


def named_forms(wanted: str, transcript: str) -> list:
    """Forms picked before the facts are known: --forms ids, else the forms named out loud ("Mishap", "OSHA form").
    Empty = nothing named → every form the facts fit (decided after the facts are found)."""
    forms = load_forms()
    if wanted:
        ids = {w.strip() for w in wanted.split(",") if w.strip()}
        unknown = ids - {f.id for f in forms}
        if unknown:
            raise ValueError(f"Unknown form(s) {sorted(unknown)}. Available: {', '.join(f.id for f in forms)}.")
        return [f for f in forms if f.id in ids]
    return forms_said(transcript, forms)


def _chosen_forms(named: list, facts: dict[str, str]) -> list:
    return named or [f for f in load_forms() if applies(f, facts)]


def missing_line(missing: list[tuple[str, str]]) -> str:
    """One line naming the preliminary boxes still blank, e.g. 'The preliminary report still needs: Local Time, …'."""
    labels = [label.split(" — ", 1)[-1] for _, label in missing]
    return f"The preliminary report still needs: {', '.join(labels)}"


def _print_form_results(results, verbose: bool = True) -> list[dict]:
    summary = []
    for result in results:
        filled = result.filled
        draft = " (DRAFT map — review)" if result.form.status != "approved" else ""
        if verbose:
            print(f"\n=== {result.form.title}{draft}: {len(filled.values)} boxes filled ===")
            for box, note in filled.notes:
                print(f"  ⚠ {box}: {note}")
            if filled.by_hand:
                print(f"  ✍ fill by hand: {', '.join(filled.by_hand)}")
            if filled.missing:
                print(f"  ⚑ {missing_line(filled.missing)}")
        summary.append({"form": result.form.id, "filled": len(filled.values), "notes": filled.notes,
                        "by_hand": filled.by_hand, "missing": filled.missing,
                        "editable_pdf": result.filled_pdf.name, "print_pdf": result.print_pdf.name})
    return summary


def file_report(transcript: str, source: str, model: str, profile: dict[str, str], records_dir: Path,
                name: str = "incident", wanted_forms: str = "", verbose: bool = True) -> tuple[Path, list]:
    """Story text → checked facts → every form that applies, filled and saved in a new folder of `records_dir`.
    Returns (the saved folder, the filled forms). This is the one path every report takes."""
    facts_template = story_template()
    named = named_forms(wanted_forms, transcript)
    if verbose:
        print(f"Forms named: {', '.join(f.id for f in named)}" if named else "No form named: every form that fits")
        print(f"Finding the facts with {model} (offline)…")
    answers = build_record(transcript, model, groups=needed_groups(named) if named else None)
    if verbose:
        for template in spoken_templates():
            print_answers(template, answers)
    facts = fact_values(answers, profile)
    forms = _chosen_forms(named, facts)
    now = datetime.now()
    folder = save_record(records_dir, name, facts_template.title, transcript, answers, source,
                         "filled (not read back)", now)
    if verbose:
        print(f"\nFilling {len(forms)} form(s): {', '.join(f.id for f in forms)}")
    results = fill_forms(forms, facts, folder, today=f"{now:%m/%d/%Y}")  # dropdowns: clear matches only
    summary = _print_form_results(results, verbose)
    write_new_private_file(folder / "forms.json", json.dumps(summary, indent=2) + "\n")
    if verbose:
        print(f"\nSaved: {folder}")
    return folder, results


def run_incident(args) -> int:
    """One story → shared incident facts (checked once) → every safety form that applies → the workbook."""
    profile = load_profile(Path(args.profile))
    if not profile:
        print(f"Note: no company profile at {args.profile}; employer boxes stay blank.")
    transcript, source = get_transcript(args, story_template())
    print(f"\n--- Transcript ({source}) ---\n{transcript}\n")
    _, results = file_report(transcript, source, args.model, profile, RECORDS_DIR, wanted_forms=args.forms)
    _update_workbook()
    speak(f"Saved. {len(results)} forms filled.")
    return 0


def _update_workbook() -> None:
    """Add the new report to data_tracker/reports.xlsx. A failure here never loses the saved report."""
    try:
        out, summary = rebuild_workbook(RECORDS_DIR)
    except (OSError, ValueError) as err:
        print(f"⚠ The workbook wasn't updated ({err}). The report is saved; run `uv run add-old-pdfs` to catch up.")
        return
    counts = ", ".join(f"{sheet} {rows}" for sheet, rows in summary.items())
    print(f"Workbook updated: {out} ({counts})")
    try:
        dashboard, _, _ = write_dashboard()
        print(f"Dashboard updated: {dashboard}")
    except OSError as err:
        print(f"⚠ The dashboard wasn't updated ({err}); run `uv run dashboard`.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", help="audio, video, or text file")
    source.add_argument("--live", action="store_true", help="talk now instead of using a file")
    source.add_argument("--list", action="store_true", help="show the forms it fills")
    source.add_argument("--brief", action="store_true", help="show what to say, then exit")
    source.add_argument("--setup", action="store_true", help="one-time download of the Whisper model (internet)")
    parser.add_argument("--forms", default="", help="only these form maps, e.g. osha_301,sd_froi (default: all)")
    parser.add_argument("--profile", default=str(PROFILE_PATH), help="company profile (typed once)")
    parser.add_argument("--hints", default="", help="names/words to spell right")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--stop-words", default="")
    parser.add_argument("--silence", type=float, default=3.0)
    args = parser.parse_args()

    if args.setup:
        print(f"Whisper model ready at: {transcriber.download_model()}")
        return 0
    if args.list:
        print("Forms (say one to fill only it; say none and every form that fits is filled):")
        for f in load_forms():
            print(f"  {f.id} [{f.status}] — say: {' / '.join(f.say) or '(no say-words)'}")
        return 0
    if args.brief:
        try:
            print(briefing(story_template()))
            print("\nForms it fills (say the form's name to fill only it):")
            for f in load_forms():
                print(f"  {f.title} — say: {' / '.join(f.say)}")
        except (FileNotFoundError, ValueError) as err:
            print(f"Stopped: {err}", file=sys.stderr)
            return 2
        return 0
    if not (args.input or args.live):
        parser.error("give --input FILE or --live")

    try:
        return run_incident(args)
    except (FileNotFoundError, ValueError) as err:
        print(f"Stopped: {err} Nothing saved.", file=sys.stderr)
        return 2
    except (ollama.ResponseError, ConnectionError) as err:
        print(f"The local AI isn't available ({err}). Start it with: brew services start ollama", file=sys.stderr)
        return 2
    except sd.PortAudioError as err:
        print(f"Couldn't use the microphone ({err}). Nothing saved.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped. Nothing saved.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
