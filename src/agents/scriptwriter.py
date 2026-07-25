"""Scriptwriter agent: topic -> ShortSpec (schema-constrained, taste-profile-aware).

MVP scope: single candidate per attempt with a regen-with-feedback loop at Gate 1.
v1 grows this to 3-5 candidates + Editor ranking + fact-checker grounding.
"""

from __future__ import annotations

import pathlib

from ..gateway.client import chat_json
from ..graph.state import ShortSpec

_PROFILE_PATH = pathlib.Path("prompts/editorial-profile.md")

SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "beats": {
            "type": "array",
            "minItems": 4,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "caption": {"type": "string"},
                    "visual_prompt": {"type": "string"},
                },
                "required": ["narration", "caption", "visual_prompt"],
                "additionalProperties": False,
            },
        },
        "payoff": {"type": "string"},
        "cta": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "minItems": 3, "maxItems": 8, "items": {"type": "string"}},
    },
    "required": ["title", "hook", "beats", "payoff", "cta", "description", "hashtags"],
    "additionalProperties": False,
}

_SYSTEM = """You write scripts for ~60-second vertical science-history Shorts.

Hard rules:
- Total spoken words (hook + all beat narrations + payoff + cta) MUST be 130-155 words. Count them.
- hook: max 12 words, no clickbait, opens a genuine curiosity gap, no "did you know".
- Each beat narration: 1-2 short spoken sentences that advance the story. Conversational, vivid, precise.
- payoff must keep the promise the hook made. cta is ONE soft line (follow/comment), never begging.
- caption per beat: max 6 punchy on-screen words, not a transcript.
- visual_prompt per beat: a concrete SDXL scene description of WHAT IS SHOWN (subject, setting, era,
  composition). Do NOT include style words (flat vector, palette etc.) - style is applied downstream.
  Never name real brands or channels. Vertical-friendly single-subject compositions.
- Only include facts you are confident are true and mainstream-documented. No invented quotes, no
  precise statistics unless certain. (A fact-checker will audit; wrong facts kill the channel.)
- title: <=90 chars, specific, no clickbait. description: 2-3 sentences. hashtags: no # symbol.

Editorial taste profile (follow it):
"""


def _profile() -> str:
    try:
        return _PROFILE_PATH.read_text(encoding="utf-8")
    except OSError:
        return "(no profile yet - use the hard rules only)"


def draft_spec(topic: str, feedback: str = "") -> ShortSpec:
    user = f"Write the spec for a short about: {topic}"
    if feedback:
        user += f"\n\nThe previous draft was rejected. Editor feedback to incorporate:\n{feedback}"
    return chat_json(
        messages=[
            {"role": "system", "content": _SYSTEM + _profile()},
            {"role": "user", "content": user},
        ],
        schema=SPEC_SCHEMA,
        schema_name="short_spec",
        temperature=0.8,
    )


def narration_text(spec: ShortSpec) -> str:
    parts = [spec["hook"]] + [b["narration"] for b in spec["beats"]] + [spec["payoff"], spec["cta"]]
    return " ".join(p.strip() for p in parts if p and p.strip())
