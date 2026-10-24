"""Transcript → profile draft, using a local AI model (Ollama). Nothing leaves the Mac.

The draft is NOT trusted as-is: every value is later checked against the user's own
words and read back for approval before it enters the profile.
"""

import json
import re
from dataclasses import replace
from typing import Any

import ollama

DEFAULT_MODEL = "gemma3:12b"  # winner of the 2026-09-27 model exam (DESIGN.md)
# Ollama's default working memory is short; long forms (dozens of fields) need room for prompt + answer
MODEL_OPTIONS = {"temperature": 0, "num_ctx": 8192}
TOKENS_PER_FIELD = 60  # a value + its quote; a normal answer never needs more


def capped(max_tokens: int) -> dict:
    """Model options with an answer-length cap, so a model stuck repeating itself is cut short."""
    return {**MODEL_OPTIONS, "num_predict": max_tokens}

PERSONAL_FIELDS = ["full_name", "email", "phone", "city", "state"]
EDUCATION_FIELDS = ["school", "degree", "field_of_study", "start", "end", "quote"]
WORK_FIELDS = ["employer", "job_title", "start", "end", "duties", "quote"]


def _object(fields: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": {f: {"type": "string"} for f in fields}, "required": fields}


SCHEMA = {
    "type": "object",
    "properties": {
        "personal": _object(PERSONAL_FIELDS),
        "education": {"type": "array", "items": _object(EDUCATION_FIELDS)},
        "work": {"type": "array", "items": _object(WORK_FIELDS)},
        "skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["personal", "education", "work", "skills"],
}

SYSTEM_PROMPT = """You fill a job-application profile from a spoken transcript.

Rules:
1. Use ONLY facts the speaker explicitly said. If something was not said, the value is exactly "".
   Never invent an email, phone, city, date, or degree. Never write "not specified", "unknown" or "N/A".
   A start year is only filled if the speaker said when they STARTED; a graduation year is an END year.
2. If the speaker corrects themself ("<wrong value>, no wait, <right value>"), use the corrected value.
3. Only include schools the speaker attended and jobs the speaker held.
   Places they only considered, applied to, or almost chose are NOT included.
4. If the speaker SAYS contact details, write them in written form: spoken "at" → @, "dot" → ., no spaces
   in emails; phone digits as digits. Spoken years ("twenty twenty") become digits.
5. A current school or job ("now", "since <year>", "I've been...") has end "present".
6. degree = the kind of degree only (e.g. PhD, bachelor's). The subject goes in field_of_study.
7. For each education/work entry, "quote" = the full sentence(s) the speaker said about it, copied exactly.
8. Skills = only abilities the speaker said they have, one per list item. Ignore filler words (um, uh, like)."""


def _chat_options(model: str) -> dict[str, Any]:
    """Models with a 'thinking' mode (e.g. Qwen3) are told not to think out loud: faster, same JSON."""
    return {"think": False} if model.startswith("qwen3") else {}


def extract_profile(transcript: str, model: str = DEFAULT_MODEL, client: ollama.Client | None = None) -> dict:
    """Ask the local model to fill the profile form from `transcript`. Returns the raw draft."""
    if not transcript.strip():
        raise ValueError("Transcript is empty; nothing to extract.")
    client = client or ollama.Client()
    response = client.chat(
        model=model,
        format=SCHEMA,
        options=MODEL_OPTIONS,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": transcript}],
        **_chat_options(model),
    )
    return json.loads(response.message.content)


# ---------- any template (reports, forms, applications) ----------

TEMPLATE_RULES = """You fill in a form from a recording's transcript. The form's fields are listed below.

Rules:
1. Use ONLY facts the speaker explicitly said. If a field was not answered, its value is exactly "".
   Never invent names, dates, times, numbers, places, or causes. Never write "unknown", "N/A" or "not stated".
2. For every non-empty value, "quote" = the exact words from the transcript that support it (copy them exactly).
3. Dates: write them as the speaker said them (e.g. "September 22, 2026"). If only a relative date was
   said ("yesterday", "last Tuesday"), use "".
4. Times: clock time only (e.g. "10:30"); AM/PM goes in its own field if the form has one.
5. Choice fields: pick one of the listed options only if the transcript clearly says so; otherwise "".
   Multi fields ("pick any"): every listed option the transcript clearly supports, separated by "; ".
6. Written sections: 1–3 plain, factual sentences using only what was said. No guesses about causes,
   no judgments, no added details.
7. If the speaker corrects themself, use the corrected value."""


_CLOCK = re.compile(r"^(\d{1,2})(?:[.:](\d{2}))?\s*(?:[ap]\.?\s?m\.?)?$", re.IGNORECASE)


def clean_value(field, value: str) -> str:
    """Tidy formats the model or Whisper get slightly wrong: time "10.30" → "10:30", "7" → "7:00"."""
    if field.kind == "time":
        match = _CLOCK.match(value)
        if match:
            return f"{int(match.group(1))}:{match.group(2) or '00'}"
    return value


def template_schema(template) -> dict[str, Any]:
    """JSON schema: every field → {value, quote}; choice values limited to their options or ""."""
    properties = {}
    for field in template.fields:
        value = {"type": "string"}
        if field.kind == "choice":
            value = {"type": "string", "enum": [*field.options, ""]}
        properties[field.key] = {
            "type": "object",
            "properties": {"value": value, "quote": {"type": "string"}},
            "required": ["value", "quote"],
        }
    return {"type": "object", "properties": properties, "required": [f.key for f in template.fields]}


def template_prompt(template) -> str:
    lines = [TEMPLATE_RULES, "", f"FORM: {template.title}", template.description]
    if template.rules:
        lines += ["", "THIS FORM'S OWN RULES (follow them):", *(f"- {r}" for r in template.rules)]
    lines += ["", "FIELDS:"]
    for field in template.fields:
        extra = f" — options: {', '.join(field.options)}" if field.kind in ("choice", "multi") else ""
        hint = f" ({field.hint})" if field.hint else ""
        hint += " (no names or personal identifiers)" if field.no_names else ""
        lines.append(f"- {field.key} [{field.kind}]: {field.label}{hint}{extra}")
    return "\n".join(lines)


def _ask_fields(transcript: str, template, model: str, client) -> dict:
    """The model's raw answer; a cut-off (looping) answer is asked again in two halves."""
    response = client.chat(
        model=model,
        format=template_schema(template),
        options=capped(200 + TOKENS_PER_FIELD * len(template.fields)),
        messages=[
            {"role": "system", "content": template_prompt(template)},
            {"role": "user", "content": f"TRANSCRIPT:\n{transcript}"},
        ],
        **_chat_options(model),
    )
    try:
        return json.loads(response.message.content)
    except json.JSONDecodeError as err:
        if len(template.fields) <= 1:
            raise ValueError("The local AI's answer was unreadable.") from err
        half = len(template.fields) // 2
        first, second = (replace(template, fields=template.fields[:half]),
                         replace(template, fields=template.fields[half:]))
        return {**_ask_fields(transcript, first, model, client), **_ask_fields(transcript, second, model, client)}


def extract_fields(
    transcript: str, template, model: str = DEFAULT_MODEL, client: ollama.Client | None = None
) -> dict[str, dict[str, str]]:
    """Ask the local model to fill `template` from `transcript`. Returns {key: {"value", "quote"}}."""
    if not transcript.strip():
        raise ValueError("Transcript is empty; nothing to fill in.")
    raw = _ask_fields(transcript, template, model, client or ollama.Client())
    return {
        f.key: {
            "value": clean_value(f, str((raw.get(f.key) or {}).get("value", "")).strip()),
            "quote": str((raw.get(f.key) or {}).get("quote", "")).strip(),
        }
        for f in template.fields
    }
