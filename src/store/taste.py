"""Taste-signal capture (ADR-0010 tier 2): append the user's editorial choices to the
signal log in prompts/editorial-profile.md, which the Scriptwriter/Editor read every run.

Append-only here; a periodic reflection pass (later) consolidates signals into the
profile's sections. Failures never block the pipeline.
"""

from __future__ import annotations

import datetime as _dt
import pathlib

_PROFILE = pathlib.Path("prompts/editorial-profile.md")


def log_signal(kind: str, detail: str) -> None:
    """kind: explicit | pick-idea | pick-script | approve | regen-feedback | reject"""
    try:
        stamp = _dt.date.today().isoformat()
        line = f"- {stamp} | {kind} | {detail.strip()[:300]}\n"
        with _PROFILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


_SECTIONS = [
    ("voice", "Voice & tone"),
    ("hooks", "Hook preferences"),
    ("structure", "Structure & pacing"),
    ("topics", "Topic taste"),
    ("hard_nos", "Hard nos"),
]

_CONSOLIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        key: {"type": "array", "minItems": 0, "maxItems": 8, "items": {"type": "string"}}
        for key, _ in _SECTIONS
    },
    "required": [key for key, _ in _SECTIONS],
    "additionalProperties": False,
}

_CONSOLIDATE_SYSTEM = """You maintain the editorial taste profile of a YouTube Shorts creator.
From the current profile document (existing bullets + the raw '## Signal log' entries), produce
the UPDATED bullet lists for each section. Condense, never hoard: merge duplicates, turn raw
signals into short actionable rules, drop one-off noise, keep existing bullets that still hold.

CRITICAL evidence rules:
- Parenthesized '(e.g. ...)' text and '- TBD' lines in the document are TEMPLATE EXAMPLES,
  not the user's preferences. NEVER turn them into rules.
- 'regen-feedback' signal entries are DIRECT USER INSTRUCTIONS - they are the strongest
  evidence and must be reflected (generalized into a rule, not quoted).
- 'pick-idea'/'pick-script' entries are weak single votes; only generalize them after
  repetition, otherwise note them as tentative ('leans toward ...').
- A section with no real evidence gets an empty list.
Plain ASCII punctuation. Each bullet is one short sentence."""

_HEADER = """# Editorial profile - the user's learned taste (read on EVERY script run)

> This file is the editorial taste model (ADR-0010). The Scriptwriter and Editor load it on
> every run. It is updated from Discord signals and consolidated via /consolidate-taste.
> Inspect with /style; correct by editing this file directly.
"""


def consolidate_profile() -> str:
    """ADR-0010 reflection pass. The model emits ONLY distilled bullets (cheap, cannot
    truncate mid-document); Python assembles the file deterministically. Returns new text."""
    from ..gateway.client import chat_json

    current = _PROFILE.read_text(encoding="utf-8")
    # Tool-over-recall: remove template bait ('(e.g. ...)' hints, TBD placeholders) from the
    # INPUT instead of instructing the model to ignore it - small models promote examples to
    # rules otherwise (observed live). Spotlight direct user instructions separately.
    kept_lines = [
        ln for ln in current.splitlines()
        if "(e.g." not in ln and "- TBD" not in ln and not ln.strip().startswith("- _(")
    ]
    feedback = [ln for ln in current.splitlines() if "| regen-feedback |" in ln or "| explicit |" in ln]
    user_msg = "\n".join(kept_lines)
    if feedback:
        user_msg += ("\n\nDIRECT USER INSTRUCTIONS (strongest evidence; each MUST become a rule "
                     "in the right section):\n" + "\n".join(feedback))
    result = chat_json(
        messages=[
            {"role": "system", "content": _CONSOLIDATE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        schema=_CONSOLIDATE_SCHEMA, schema_name="taste", temperature=0.2, max_tokens=1200,
        timeout_s=600.0,
    )
    # Keep the 5 most recent raw signal lines from the current file.
    recent = [ln for ln in current.splitlines() if ln.startswith("- 20")][-5:]
    parts = [_HEADER, f"\n_Last updated: {_dt.date.today().isoformat()} (consolidated)._\n"]
    for key, heading in _SECTIONS:
        bullets = result.get(key) or []
        parts.append(f"\n## {heading}\n" + "".join(f"- {b.strip()}\n" for b in bullets))
    parts.append("\n## Signal log (append-only; consolidated periodically)\n"
                 + "".join(ln + "\n" for ln in recent))
    new_text = "".join(parts)
    if sum(len(result.get(k) or []) for k, _ in _SECTIONS) == 0:
        raise RuntimeError("consolidation produced zero bullets; keeping the old profile")
    _PROFILE.with_suffix(".md.bak").write_text(current, encoding="utf-8")
    _PROFILE.write_text(new_text, encoding="utf-8")
    return new_text


def profile_text() -> str:
    try:
        return _PROFILE.read_text(encoding="utf-8")
    except OSError:
        return "(no profile yet)"
