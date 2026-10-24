"""One story → one incident record → every safety form that applies.

The facts are found and proof-checked ONCE (from the recording; company facts come from the saved profile unless
the company name is said); each form then takes what it needs, so all forms say the same thing.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path

import ollama
import yaml

from vff.ampm import fill_ampm
from vff.boxes import read_boxes
from vff.extract import DEFAULT_MODEL, _chat_options, capped, extract_fields
from vff.formats import apply_formats, format_value
from vff.forms import FACTS_PATH, FilledForm, FormMap, Picker, form_values
from vff.grounding import check_answers
from vff.paths import DATA_DIR
from vff.pdf_fill import fill_pdf, print_pdf
from vff.templates import Template, load_template

PROFILE_PATH = DATA_DIR / "profile.yaml"
COMPANY_DESCRIPTION = ("The company this report is for — only what is said about the company itself. "
                       "Leave everything blank if the company's own name is not said.")


@dataclass(frozen=True)
class FormResult:
    form: FormMap
    filled: FilledForm
    filled_pdf: Path
    print_pdf: Path


def story_template(facts_path: Path = FACTS_PATH) -> Template:
    """The facts that are always said in the recording (not company facts)."""
    facts = load_template(facts_path)
    return replace(facts, fields=tuple(f for f in facts.fields if f.group == "story"))


def company_template(facts_path: Path = FACTS_PATH) -> Template:
    """The company facts, asked as their own short question so the story question stays the same."""
    facts = load_template(facts_path)
    return replace(facts, description=COMPANY_DESCRIPTION, rules=(),
                   fields=tuple(f for f in facts.fields if f.group == "company"))


def company_keys(facts_path: Path = FACTS_PATH) -> frozenset[str]:
    return frozenset(f.key for f in company_template(facts_path).fields)


def build_record(transcript: str, model: str = DEFAULT_MODEL, client=None,
                 facts_path: Path = FACTS_PATH) -> dict[str, dict]:
    """Story → checked facts: AI draft, proof check against the words, AM/PM, formats.
    Then the company facts, in case the company's own details are said."""
    answers = {}
    for template in (story_template(facts_path), company_template(facts_path)):
        draft = extract_fields(transcript, template, model=model, client=client)
        checked = fill_ampm(template, check_answers(template, draft, transcript), transcript)
        answers |= apply_formats(template, checked, pdf_formats={})
    return answers


def load_profile(path: Path = PROFILE_PATH, facts_path: Path = FACTS_PATH) -> dict[str, str]:
    """The company profile (typed once). Only company facts are allowed; values are written in their format."""
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    company = {f.key: f for f in load_template(facts_path).fields if f.key in company_keys(facts_path)}
    wrong = sorted(k for k in raw if k not in company)
    if wrong:
        raise ValueError(f"{path.name}: not company facts: {wrong} (allowed: {sorted(company)})")
    return {k: format_value(company[k].format, str(v).strip()) for k, v in raw.items() if str(v).strip()}


def fact_values(answers: dict[str, dict], profile: dict[str, str]) -> dict[str, str]:
    """Plain fact → value, leaving out anything the proof check rejected."""
    said = {k: a["value"] for k, a in answers.items() if a.get("value") and a.get("check") != "unsupported"}
    return with_company(said, profile)


def with_company(facts: dict[str, str], profile: dict[str, str]) -> dict[str, str]:
    """Company name said → the spoken company details; not said → the profile (the default company).
    Never mixed, so one company's name can't go out with another company's tax ID."""
    if facts.get("employer_name"):
        return facts
    company = company_keys()
    return {**{k: v for k, v in facts.items() if k not in company}, **profile}


def ai_picker(model: str = DEFAULT_MODEL, client=None) -> Picker:
    """For coded lists the simple match can't read ("slipped on a wet floor" → "29 Fall from same level")."""
    client = client or ollama.Client()

    def pick(question: str, value: str, options: tuple[str, ...]) -> str:
        schema = {"type": "object", "properties": {"option": {"type": "string", "enum": [*options, ""]}},
                  "required": ["option"]}
        prompt = (f"Form box: {question}\nWhat was said: {value}\n"
                  "Pick the one option that clearly fits what was said, or \"\" if none clearly fits.")
        response = client.chat(model=model, format=schema, options=capped(100),
                               messages=[{"role": "user", "content": prompt}], **_chat_options(model))
        return json.loads(response.message.content).get("option", "")

    return pick


def fill_forms(forms: list[FormMap], facts: dict[str, str], folder: Path, today: str,
               picker: Picker | None = None) -> list[FormResult]:
    """Fill every form from the same facts; each gets an editable and a print copy in `folder`."""
    results = []
    for form in forms:
        boxes = {b.name: b for b in read_boxes(form.pdf_path)}
        filled = form_values(form, facts, boxes, today, picker)
        editable = fill_pdf(form.pdf_path, filled.values, Path(folder) / f"{form.id}_filled.pdf")
        printed = print_pdf(form.pdf_path, filled.values, Path(folder) / f"{form.id}_print.pdf")
        results.append(FormResult(form, filled, editable, printed))
    return results
