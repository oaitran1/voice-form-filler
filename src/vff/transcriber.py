"""Speech → text with Whisper (large-v3-turbo), running entirely on this computer.

Apple Silicon Macs use Apple MLX; Windows, Linux and Intel Macs use faster-whisper. Same model, same settings.
"""

import os
import platform
import sys
from functools import cache

import numpy as np

APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"
MODEL = "mlx-community/whisper-large-v3-turbo" if APPLE_SILICON else "large-v3-turbo"
SAMPLE_RATE = 16_000  # Whisper expects 16 kHz mono audio


def go_offline() -> None:
    """Forbid any network calls for model files. Call before transcribing."""
    os.environ["HF_HUB_OFFLINE"] = "1"


def download_model() -> str:
    """One-time download of the Whisper model (the only step that uses internet)."""
    if APPLE_SILICON:
        from huggingface_hub import snapshot_download

        return snapshot_download(MODEL)
    from faster_whisper import download_model as fw_download

    return fw_download(MODEL)


@cache
def _faster_whisper_model():
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL, device="auto", compute_type="default", local_files_only=True)


def transcribe(audio: np.ndarray | str, language: str | None = "en", hint_words: str = "") -> str:
    """Turn audio (16 kHz float32 array, or a file path) into text.

    `hint_words` (e.g. "Sam Park, Greenville") nudges Whisper toward correct spellings.
    """
    settings = {
        "language": language,
        "condition_on_previous_text": False,  # reduces made-up repeated text
        "initial_prompt": hint_words or None,
    }
    if APPLE_SILICON:
        import mlx_whisper

        return str(mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, **settings)["text"]).strip()
    segments, _ = _faster_whisper_model().transcribe(audio, **settings)
    return " ".join(s.text.strip() for s in segments).strip()
