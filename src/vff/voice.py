"""Talking with the user: wait for the start cue, listen to one turn. Shared by every command."""

import queue
import sys
import threading

from vff import transcriber
from vff.recorder import PauseCheck, record_until_done
from vff.triggers import DEFAULT_START_PHRASES, after_start_phrase, ends_with_stop_phrase, strip_stop_phrase

ANSWER_SILENCE_SECONDS = 1.5
ANSWER_WAIT_SECONDS = 8.0
ASK_ATTEMPTS = 2
START_WAIT_SECONDS = 120.0  # one listen for "start recording" waits this long for any speech, then listens again


def stop_phrase_check(phrases: tuple[str, ...], hints: str) -> PauseCheck:
    """At each pause, transcribe the last few seconds and look for a stop phrase."""
    return lambda recent_audio: ends_with_stop_phrase(transcriber.transcribe(recent_audio, hint_words=hints), phrases)


_ENTER: "queue.Queue[str]" = queue.Queue()  # every Enter pressed, read by one helper thread
_reader_started = False


def start_on_enter_or_phrase(hints: str, on_heard=None, starts_story=None) -> str:
    """Wait for the start cue: Enter, saying "start recording", or words that `starts_story(text)` accepts as the
    story's own opening (e.g. a form's name) — those words are kept and returned. An Enter pressed earlier (while
    forms were being filled) does not count."""
    global _reader_started
    if not _reader_started:
        threading.Thread(target=lambda: [_ENTER.put(line) for line in sys.stdin], daemon=True).start()
        _reader_started = True
    while not _ENTER.empty():
        _ENTER.get_nowait()
    return wait_for_start(hints, pressed=lambda: not _ENTER.empty(), on_heard=on_heard, starts_story=starts_story)


def wait_for_start(hints: str, pressed=None, on_heard=None,
                   phrases: tuple[str, ...] = DEFAULT_START_PHRASES, starts_story=None) -> str:
    """Wait until "start recording" is said, `pressed()` turns true (Enter), or `starts_story(text)` says the words
    heard are the story's opening (returned whole). Otherwise returns what was said after the phrase in the same
    breath (usually ''). Anything else heard is shown through `on_heard` and ignored."""
    while not (pressed and pressed()):
        audio, reason = record_until_done(ANSWER_SILENCE_SECONDS, wait_for_speech_seconds=START_WAIT_SECONDS,
                                          max_seconds=30.0, cancel=pressed)
        if reason in ("no_speech", "cancelled"):
            continue
        text = transcriber.transcribe(audio, hint_words=hints)
        del audio
        rest = after_start_phrase(text, phrases)
        if rest is not None:
            return rest
        if starts_story and text and starts_story(text):
            return text
        if on_heard:
            on_heard(text)
    return ""


def listen(
    silence_seconds: float, hints: str, wait_seconds: float = 15.0, phrases: tuple[str, ...] = ()
) -> str | None:
    """Record one turn and return its text (stop phrase removed), or None if nothing was said."""
    on_pause = stop_phrase_check(phrases, hints) if phrases else None
    audio, reason = record_until_done(silence_seconds, wait_for_speech_seconds=wait_seconds, on_pause=on_pause)
    if reason == "no_speech":
        return None
    text = transcriber.transcribe(audio, hint_words=hints)
    del audio  # drop the recording as soon as it has become text
    if phrases:
        text = strip_stop_phrase(text, phrases)
    return text or None

