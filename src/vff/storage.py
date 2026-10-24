"""Save transcripts in one private folder that only the user's account can read."""

import os
from datetime import datetime
from pathlib import Path

FOLDER_MODE = 0o700  # owner only: read, write, open
FILE_MODE = 0o600  # owner only: read, write


def private_folder(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(FOLDER_MODE)
    return folder


def write_new_private_file(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def save_transcript(text: str, folder: Path, now: datetime) -> Path:
    """Write `text` to a new, owner-only file; never overwrites an older transcript."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Transcript is empty; nothing to save.")

    folder = private_folder(Path(folder))
    stem = f"transcript_{now:%Y-%m-%d_%H%M%S}"
    path = folder / f"{stem}.txt"
    counter = 2
    while path.exists():
        path = folder / f"{stem}_{counter}.txt"
        counter += 1

    write_new_private_file(path, cleaned + "\n")
    return path
