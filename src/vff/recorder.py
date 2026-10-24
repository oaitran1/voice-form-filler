"""Record from the microphone into memory only. Audio is never written to disk."""

import queue
from dataclasses import replace
from typing import Callable

import numpy as np
import sounddevice as sd

from vff.silence import RecordingState, SilenceRule, just_paused, rms, step, threshold_from_noise
from vff.transcriber import SAMPLE_RATE

CHUNK_SECONDS = 0.1
CALIBRATE_SECONDS = 0.5
PAUSE_SECONDS = 0.8  # a short pause triggers a stop-phrase check
TAIL_SECONDS = 4.0  # how much recent audio the stop-phrase check listens to
MIC_TIMEOUT_SECONDS = 5.0

PauseCheck = Callable[[np.ndarray], bool]  # recent audio → True means "stop now"


def _next_chunk(chunks_in: "queue.Queue[np.ndarray]") -> np.ndarray:
    try:
        return chunks_in.get(timeout=MIC_TIMEOUT_SECONDS)
    except queue.Empty as err:
        raise RuntimeError("The microphone stopped sending audio.") from err


def record_until_done(
    silence_seconds: float = 3.0,
    wait_for_speech_seconds: float = 15.0,
    max_seconds: float = 300.0,
    on_pause: PauseCheck | None = None,
    cancel: Callable[[], bool] | None = None,
) -> tuple[np.ndarray, str]:
    """Listen until the user is done. Returns (audio, stop_reason).

    Stops on: a stop phrase (checked by `on_pause` at each short pause), a long silence,
    no speech at all, the maximum length, or `cancel()` turning true (e.g. Enter was pressed) → "cancelled". Audio is buffered in a queue by the mic
    callback, so nothing is lost while `on_pause` is thinking.
    Raises sounddevice.PortAudioError if no microphone is available or access is denied.
    """
    blocksize = int(SAMPLE_RATE * CHUNK_SECONDS)
    tail_chunks = int(TAIL_SECONDS / CHUNK_SECONDS)
    chunks_in: "queue.Queue[np.ndarray]" = queue.Queue()

    def on_audio(indata, _frames, _time, _status) -> None:
        chunks_in.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=blocksize, callback=on_audio):
        noise = [rms(_next_chunk(chunks_in)) for _ in range(int(CALIBRATE_SECONDS / CHUNK_SECONDS))]
        rule = SilenceRule(threshold_from_noise(noise), silence_seconds, wait_for_speech_seconds, max_seconds)
        state, chunks = RecordingState(), []
        while state.stop_reason is None:
            if cancel and cancel():
                state = replace(state, stop_reason="cancelled")
                break
            chunk = _next_chunk(chunks_in)
            chunks.append(chunk)
            new = step(state, rms(chunk), CHUNK_SECONDS, rule)
            if on_pause and new.stop_reason is None and just_paused(state, new, PAUSE_SECONDS):
                if on_pause(np.concatenate(chunks[-tail_chunks:])):
                    new = replace(new, stop_reason="stop_phrase")
            state = new
    return (np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")), state.stop_reason
