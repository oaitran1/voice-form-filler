"""Where the project's folders are. Code lives in src/vff/; forms, private data and saved records sit at the top."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # src/vff/paths.py → the project folder
TEMPLATES_DIR = ROOT / "templates"
FORMS_DIR = TEMPLATES_DIR / "forms"  # one PDF + one .yaml per form
DATA_DIR = ROOT / "data"  # private: company profile (gitignored)
RECORDS_DIR = ROOT / "records"  # private: saved stories and filled PDFs (gitignored)
DATA_TRACKER_DIR = ROOT / "data_tracker"  # private: the Excel files built from the saved PDFs (gitignored)
