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
        # Hook taxonomy (R&D 4.8): typed hooks let the Editor critique the TYPE and the
        # taste profile learn which types this audience rewards, not just verbatim quotes.
        "hook_type": {"type": "string",
                      "enum": ["question", "surprising_fact", "bold_claim",
                               "whats_wrong_here", "myth_bust"]},
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
                    "archival_subject": {"type": "string"},
                },
                "required": ["narration", "caption", "visual_prompt", "archival_subject"],
                "additionalProperties": False,
            },
        },
        "payoff": {"type": "string"},
        "cta": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "minItems": 3, "maxItems": 8, "items": {"type": "string"}},
    },
    "required": ["title", "hook", "hook_type", "beats", "payoff", "cta", "description", "hashtags"],
    "additionalProperties": False,
}

_SYSTEM = """You write scripts for ~60-second vertical science-history Shorts.

Hard rules:
- Total spoken words (hook + all beat narrations + payoff + cta) MUST be 160-175 words. Count them.
  (Calibrated 2026-08-08 against the real narration rate of 2.9 words/sec: 130-155 produced
  48-56s videos; 160-175 lands the true ~60s target.)
- hook: max 12 words, no clickbait, opens a genuine curiosity gap, no "did you know".
- hook_type: classify the hook honestly as question / surprising_fact / bold_claim /
  whats_wrong_here / myth_bust, and write the hook so it genuinely fits that type.
- Each beat narration: 2-3 short spoken sentences that advance the story with CONCRETE detail
  from the evidence (a name, a place, a mechanism, a vivid specific) - never filler to hit the
  word count. Conversational, vivid, precise.
- payoff must keep the promise the hook made. cta is ONE soft line (follow/comment), never begging.
- caption per beat: max 6 punchy on-screen words, not a transcript.
- visual_prompt per beat: a concrete SDXL scene description of WHAT IS SHOWN (subject, setting, era,
  composition). Do NOT include style words (flat vector, palette etc.) - style is applied downstream.
  Never name real brands or channels. Vertical-friendly single-subject compositions.
- archival_subject per beat: if a REAL archival image would teach this beat better than an
  illustration (a specific apparatus, an anatomical plate, an astronomy photo, a historical
  document), give a 2-4 word archive search term (e.g. "Leyden jar", "Voyager golden record").
  Otherwise EMPTY STRING. Use sparingly - most beats should stay illustrated.
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


def draft_spec(topic: str, feedback: str = "", evidence_text: str = "") -> ShortSpec:
    user = f"Write the spec for a short about: {topic}"
    if evidence_text:
        user += (
            "\n\nEVIDENCE PACK (ground every factual claim in this; if a detail is not here "
            "and you are not certain of it, leave it out):\n" + evidence_text
        )
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


_ANGLES = [
    "Angle: STORY-FIRST - open on the human moment, unfold chronologically.",
    "Angle: SURPRISE-FIRST - lead with the most counterintuitive fact, then explain it.",
    "Angle: STAKES-FIRST - open with what was at risk or what the world got wrong.",
]


def _budget_violations(spec: ShortSpec) -> list[str]:
    """Deterministic per-field word budgets (R&D 4.8): structure the prompt merely asks
    for lives in CODE, mirroring the Visual Director's validator pattern. Trigger ranges
    are looser than the prompt's targets so marginal drafts don't burn the one retry."""
    v = []
    hook_words = len(spec["hook"].split())
    if hook_words > 12:
        v.append(f"hook is {hook_words} words (max 12)")
    for i, b in enumerate(spec["beats"]):
        w = len(b["narration"].split())
        if not 10 <= w <= 50:
            v.append(f"beat {i} narration is {w} words (want roughly 20-45)")
    total = len(narration_text(spec).split())
    # 2026-08-08 recalibration: measured 2.90 spoken words/sec -> 160-175 words = ~60s video.
    # The old 130-155 target (accept 110-170) shipped 48s shorts.
    if not 150 <= total <= 190:
        v.append(f"total spoken words {total} (target 160-175 for a true 60s video)")
    return v


def draft_candidates(topic: str, feedback: str = "", evidence_text: str = "", n: int = 3) -> list[ShortSpec]:
    """N angle-varied candidates. One corrective retry per candidate when it breaks the
    word budgets (was: only when badly short overall)."""
    out = []
    for i in range(n):
        angle_feedback = (_ANGLES[i % len(_ANGLES)] + " " + feedback).strip()
        spec = draft_spec(topic, angle_feedback, evidence_text)
        problems = _budget_violations(spec)
        if problems:
            spec = draft_spec(
                topic,
                f"{angle_feedback} Previous draft broke the word budgets: {'; '.join(problems)}. "
                "Fix every violation while keeping the story concrete and evidence-backed.",
                evidence_text,
            )
        out.append(spec)
    return out
