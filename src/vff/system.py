"""The few things done differently on Mac, Windows and Linux: speaking aloud and opening a file or folder."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def speak(text: str) -> None:
    """Say `text` aloud with the computer's built-in offline voice. Silent if there is none (it is also printed)."""
    if sys.platform == "darwin":
        command = ["say", text]
    elif sys.platform == "win32":
        quoted = text.replace("'", "''")
        command = ["powershell", "-NoProfile", "-Command",
                   f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{quoted}')"]
    elif voice := shutil.which("spd-say") or shutil.which("espeak-ng") or shutil.which("espeak"):
        command = [voice, "--wait", text] if voice.endswith("spd-say") else [voice, text]
    else:
        return
    subprocess.run(command, check=False, capture_output=True)


def show(path: Path) -> None:
    """Open a file or folder in the computer's usual app (PDF viewer, Finder / Explorer / file manager)."""
    if sys.platform == "win32":
        os.startfile(path)  # opens our own saved file
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        if shutil.which(opener):
            subprocess.run([opener, str(path)], check=False, capture_output=True)
