"""Save each report as a private record folder of plain-text files, plus one index for searching.

records/
  index.jsonl                               ← one line per record (for search)
  2026-09-27_160500_osha_301/
    transcript.txt                          ← what was said
    record.json                             ← every field: value, the quote it came from, proof-check result
    filled.pdf                              ← the filled form (if the template has one)
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from vff.storage import FILE_MODE, FOLDER_MODE, private_folder, write_new_private_file

INDEX_NAME = "index.jsonl"
SUMMARY_MAX_CHARS = 160


def _new_record_folder(records_dir: Path, base: str) -> Path:
    folder, counter = records_dir / base, 2
    while folder.exists():
        folder, counter = records_dir / f"{base}_{counter}", counter + 1
    folder.mkdir(mode=FOLDER_MODE)
    folder.chmod(FOLDER_MODE)
    return folder


def _append_private_line(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, FILE_MODE)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _summary(fields: dict[str, dict]) -> dict[str, str]:
    return {
        key: str(f["value"])[:SUMMARY_MAX_CHARS]
        for key, f in fields.items()
        if f.get("value") and f.get("check") != "unsupported"
    }


def delete_record(records_dir: Path, name: str) -> bool:
    """Throw away the record folder `name` and its index line — a run stopped before it finished. True if it was there."""
    records_dir = Path(records_dir)
    folder = records_dir / name
    if not name or "/" in name or name in (".", "..") or not folder.is_dir():
        return False
    shutil.rmtree(folder)
    index = records_dir / INDEX_NAME
    if index.is_file():
        kept = [line for line in index.read_text(encoding="utf-8").splitlines() if _entry_id(line) != name]
        tmp = index.with_suffix(".tmp")
        tmp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
        tmp.chmod(FILE_MODE)
        os.replace(tmp, index)
    return True


def _entry_id(line: str) -> str:
    try:
        entry = json.loads(line)
    except ValueError:
        return ""
    return str(entry.get("id", "")) if isinstance(entry, dict) else ""


def save_record(
    records_dir: Path,
    template_id: str,
    template_title: str,
    transcript: str,
    fields: dict[str, dict],
    source: str,
    status: str,
    now: datetime,
) -> Path:
    """Write a new record folder (never overwrites) and add it to the index. Returns the folder."""
    records_dir = private_folder(Path(records_dir))
    folder = _new_record_folder(records_dir, f"{now:%Y-%m-%d_%H%M%S}_{template_id}")
    created = now.isoformat(timespec="seconds")
    record = {
        "id": folder.name,
        "template": template_id,
        "template_title": template_title,
        "created": created,
        "source": source,
        "status": status,
        "fields": fields,
    }
    write_new_private_file(folder / "transcript.txt", transcript.strip() + "\n")
    write_new_private_file(folder / "record.json", json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    entry = {
        "id": folder.name,
        "template": template_id,
        "created": created,
        "status": status,
        "source": source,
        "summary": _summary(fields),
    }
    _append_private_line(records_dir / INDEX_NAME, json.dumps(entry, ensure_ascii=False))
    return folder
