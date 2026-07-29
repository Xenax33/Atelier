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
