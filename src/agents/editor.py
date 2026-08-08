"""Editor agent: critique and rank candidate scripts against the editorial profile.

The Editor is the retention-and-taste critic; the fact-checker handles truth. Its top
pick gets audited and recommended at Gate 1, but the human sees all candidates.
"""

from __future__ import annotations

from ..gateway.client import chat_json
from .scriptwriter import _profile, narration_text

RANK_SCHEMA = {
    "type": "object",
    "properties": {
        "best": {"type": "integer", "minimum": 0, "maximum": 4},
        "critiques": {
            "type": "array", "minItems": 1, "maxItems": 5,
            "items": {"type": "string"},
        },
    },
    "required": ["best", "critiques"],
    "additionalProperties": False,
}

_SYSTEM = """You are the showrunner/editor of a science-history Shorts channel. Judge candidate
scripts for RETENTION and fit to the editorial profile: hook strength in the first 2 seconds,
a pattern-interrupt or surprise early, concrete vivid detail over generalities, a payoff that
keeps the hook's promise, correct length (160-175 spoken words = a true 60s video), and no clickbait.

Return the index of the best candidate and ONE punchy critique sentence per candidate
(in order), each naming the single biggest strength or weakness. Each hook carries a
declared type (question / surprising_fact / bold_claim / whats_wrong_here / myth_bust) -
when the hook is the strength or weakness, name its type in the critique so the taste
profile learns which types land.

Editorial profile:
"""


def rank_candidates(candidates: list[dict]) -> dict:
    blocks = []
    for i, c in enumerate(candidates):
        words = len(narration_text(c).split())
        beats = " / ".join(b["narration"] for b in c["beats"])
        blocks.append(
            f"[{i}] TITLE: {c['title']}\nHOOK ({c.get('hook_type', 'untyped')}): {c['hook']}\n"
            f"BEATS: {beats}\nPAYOFF: {c['payoff']} ({words} words)"
        )
    result = chat_json(
        messages=[
            {"role": "system", "content": _SYSTEM + _profile()},
            {"role": "user", "content": "\n\n".join(blocks)},
        ],
        schema=RANK_SCHEMA, schema_name="ranking", temperature=0.3, max_tokens=700,
    )
    result["best"] = min(result["best"], len(candidates) - 1)
    while len(result["critiques"]) < len(candidates):
        result["critiques"].append("")
    return result
