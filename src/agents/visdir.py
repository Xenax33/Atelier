"""Visual Director agent: translate approved narration into DEPICTABLE SDXL scenes.

Exists because of a measured failure (run 20260729-a8fea8): scriptwriter prompts asked
SDXL for numbers, formulas, and abstractions - things diffusion models cannot render
(and our negative prompt rightly bans text). Result: style-only "random shapes".
The Director's whole job is the translation: concept -> concrete physical scene.
Numbers/formulas belong to the caption/Manim layer, never to SDXL.
"""

from __future__ import annotations

from ..gateway.client import chat_json

_SCHEMA = {
    "type": "object",
    "properties": {
        "prompts": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string"}},
        "has_people": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "boolean"}},
    },
    "required": ["prompts", "has_people"],
    "additionalProperties": False,
}

_SYSTEM = """You are the visual director for illustrated 60-second science Shorts. For each beat's
narration, write ONE image-generation prompt describing a CONCRETE, PHYSICALLY DEPICTABLE scene.

ABSOLUTE RULES (the image model CANNOT render these; asking produces garbage):
- NEVER request text, letters, numbers, digits, formulas, equations, labels, charts, graphs,
  number lines, or screens showing data. Numbers live in the caption layer, not the image.
- NEVER request abstract concepts directly ("infinity", "a pattern", "an idea", "numbers flowing").
  Translate them into physical metaphors a painter could paint: a spiral staircase descending to
  one glowing door; a marble rolling down a funnel; a locksmith facing a wall of locks.

EVERY prompt must contain, in this order:
1. ONE main subject (a person, creature, object, or place - specific and era-appropriate).
2. What the subject is doing (a single clear action or state).
3. The setting and lighting (time of day, place, mood).
4. A composition hint for a vertical 9:16 frame.
Keep each under 40 words. No style words (style is applied downstream). No brand names.
Also return has_people: for each prompt, true if any person/figure appears in the scene
(style routing: people-free scenes may render more realistically).

WORKED EXAMPLES of the required translation:
- narration "every number ever tested shrinks down to 1" ->
  "A single marble rolling down a huge spiral funnel toward one glowing exit at the bottom,
   dim workshop, dramatic overhead light, centered, tall vertical composition"
- narration "mathematicians checked two trillion cases" ->
  "A lone researcher with a lantern facing an endless dark archive of drawers stretching to
   the ceiling, night, low wide angle making the shelves tower"
- narration "the formula is simple: halve it or triple it and add one" ->
  "A pair of old brass balance scales on a workbench, one pan low one pan high, warm
   candlelight, close-up, centered"."""

_BANNED = ("number", "digit", "formula", "equation", "chart", "graph", "screen",
           "text", "letter", "label", "diagram")


def _violations(prompts: list[str]) -> list[int]:
    import re

    bad = []
    for i, p in enumerate(prompts):
        low = p.lower()
        # Era descriptors are legitimate style cues, not renderable-text requests.
        stripped = re.sub(r"\b1[0-9]{3}s?\b|\b\d{1,2}(st|nd|rd|th)\s+century\b", "", low)
        if re.search(r"\d", stripped) or any(w in stripped for w in _BANNED):
            bad.append(i)
    return bad


def direct_visuals(beats: list[dict], topic: str) -> tuple[list[str], list[bool]]:
    """Returns (prompts, has_people) per beat, same order. Deterministically validated:
    prompts containing digits or banned concepts trigger corrective retries. Raises on
    failure (caller falls back to the scriptwriter's original prompts + painterly style)."""
    # Narration ONLY - the writer's draft prompts anchor small models into editing instead
    # of translating (observed live: every number/formula survived the first design).
    lines = "\n".join(f"[{i}] {b['narration']}" for i, b in enumerate(beats))
    user = (f"Topic: {topic}\n\nBeat narrations:\n{lines}\n\n"
            f"Return exactly {len(beats)} prompts, in order.")
    messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    result = chat_json(messages, _SCHEMA, "visual_prompts", temperature=0.6, max_tokens=1200)
    prompts = result["prompts"]
    for _round in range(2):
        bad = _violations(prompts)
        if not bad:
            break
        offenders = "\n".join(f"[{i}] {prompts[i]}" for i in bad)
        messages.append({"role": "assistant", "content": "\n".join(prompts)})
        messages.append({"role": "user", "content":
                         "These prompts VIOLATE the absolute rules (digits or banned concepts like "
                         f"numbers/formulas/labels/screens):\n{offenders}\nRewrite ALL {len(beats)} "
                         "prompts; replace every violation with a physical metaphor per the worked "
                         "examples (objects and people only, nothing that implies written symbols)."})
        result = chat_json(messages, _SCHEMA, "visual_prompts", temperature=0.7, max_tokens=1200)
        prompts = result["prompts"]
    if len(prompts) < len(beats):
        prompts += [b.get("visual_prompt", "") for b in beats[len(prompts):]]
    people = list(result.get("has_people", [])) + [True] * len(beats)  # default safe: True
    return prompts[: len(beats)], people[: len(beats)]
