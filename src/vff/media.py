"""Any recording or note → transcript text. Audio and video are transcribed offline with Whisper."""

from pathlib import Path

from vff import transcriber

TEXT_TYPES = frozenset({".txt", ".md"})
AUDIO_VIDEO_TYPES = frozenset({
    ".m4a", ".mp3", ".wav", ".aiff", ".aif", ".aac", ".caf", ".flac", ".ogg", ".opus",  # audio / voice memos
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi",  # video (only the sound is used)
})


def transcript_from_file(path: Path, hints: str = "") -> str:
    """Read a text file as-is, or transcribe an audio/video file (ffmpeg extracts the sound)."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No file at {path}")
    suffix = path.suffix.lower()
    if suffix in TEXT_TYPES:
        return path.read_text(encoding="utf-8").strip()
    if suffix in AUDIO_VIDEO_TYPES:
        transcriber.go_offline()
        return transcriber.transcribe(str(path), hint_words=hints)
    supported = ", ".join(sorted(TEXT_TYPES | AUDIO_VIDEO_TYPES))
    raise ValueError(f"Unsupported file type {suffix!r}. Supported: {supported}")
