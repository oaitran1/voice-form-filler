"""Decide when to stop recording, so the user never has to press a button.

Recording stops when the user has spoken and then been quiet for a while,
when nobody speaks at all, or when a maximum length is reached.
"""

from dataclasses import dataclass, replace
from statistics import median
from typing import Sequence

import numpy as np

EPSILON = 1e-9  # guards against float drift when summing chunk durations
MIN_THRESHOLD = 0.01
NOISE_FACTOR = 3.0


@dataclass(frozen=True)
class SilenceRule:
    threshold: float
    silence_seconds: float = 3.0
    wait_for_speech_seconds: float = 15.0
    max_seconds: float = 300.0


@dataclass(frozen=True)
class RecordingState:
    elapsed: float = 0.0
    heard_speech: bool = False
    quiet_for: float = 0.0
    stop_reason: str | None = None  # "done" | "no_speech" | "max_length"


def rms(chunk: np.ndarray) -> float:
    """Loudness of one audio chunk (root mean square)."""
    return float(np.sqrt(np.mean(np.square(chunk))))


def threshold_from_noise(levels: Sequence[float]) -> float:
    """Pick a speech threshold a few times louder than the room's background noise."""
    return max(MIN_THRESHOLD, NOISE_FACTOR * median(levels))


def just_paused(before: RecordingState, after: RecordingState, pause_seconds: float) -> bool:
    """True exactly once per pause: the moment quiet time after speech reaches `pause_seconds`."""
    return (
        after.heard_speech
        and before.quiet_for + EPSILON < pause_seconds
        and after.quiet_for + EPSILON >= pause_seconds
    )


def step(state: RecordingState, level: float, chunk_seconds: float, rule: SilenceRule) -> RecordingState:
    """Return the next recording state after one chunk; never mutates `state`."""
    elapsed = state.elapsed + chunk_seconds
    if level >= rule.threshold:
        heard_speech, quiet_for = True, 0.0
    else:
        heard_speech = state.heard_speech
        quiet_for = state.quiet_for + chunk_seconds if heard_speech else 0.0

    stop_reason = None
    if heard_speech and quiet_for + EPSILON >= rule.silence_seconds:
        stop_reason = "done"
    elif not heard_speech and elapsed + EPSILON >= rule.wait_for_speech_seconds:
        stop_reason = "no_speech"
    elif elapsed + EPSILON >= rule.max_seconds:
        stop_reason = "max_length"

    return replace(
        state, elapsed=elapsed, heard_speech=heard_speech, quiet_for=quiet_for, stop_reason=stop_reason
    )
