# 0008 - Flat-vector / illustrative visual style (+ Manim diagrams)
Status: Accepted
Date: 2026-07-22
_User decision (2026-07-22): "Flat-vector + diagrams"._

## Context
Visual options: flat-vector/illustrative (TED-Ed/Kurzgesagt feel), diagram-forward, semi-photoreal, or mixed.
Style choice affects consistency, render cost, licensing, and AI-disclosure risk.

## Decision
Adopt a **flat-vector illustrative** house style via **SDXL + style LoRAs**, combined with **Manim** animated
diagrams/timelines. Never name real brands/channels in prompts (generic style descriptors only).

## Consequences
- Easy: consistent look across a video via LoRAs; license-clean; **avoids YouTube's realistic-person disclosure
  risk entirely**; diagrams are the science niche's differentiator.
- Hard: need to curate/train a style LoRA for consistency; less "wow" than cinematic realism.
- Revisit when: brand identity evolves, or NVIDIA enables richer motion.

## Alternatives rejected
- **Semi-photoreal** - harder consistency, higher render time, more disclosure/likeness risk.
- **Mixed per-video** - weaker brand consistency early; more prompt/LoRA management.

## Amendment (2026-08-08): per-style checkpoints + AYS 12-step schedule adopted
Same-seed A/B session (timings + verdicts in tasks/ledger TASK-037): painterly now renders on
**DreamShaper XL 1.0** (true painted light/texture vs base's flat outlines) and cinematic on
**RealVisXL V5.0** (photographic depth), both OpenRAIL++ (license-verified at source, research
doc section 9); the retired vector preset stays on SDXL base (its LoRA was tuned there).
Sampling switched to **Align-Your-Steps at 12 steps**: quality on par with 32/karras at 2.6x
speed (~118s vs ~315s warm), verified independently AND combined with the new checkpoints.
PAG stays on. Hires-fix was REJECTED as-shipped (frame-wide smearing) - flag stays off with
retune notes in workers/visuals.py.

## Amendment (2026-08-02): smart-routed painterly/cinematic replaces flat-vector default
User decision after a three-way same-seed style comparison: flat vector looked underrefined.
New default: **painterly storybook** for any scene containing people (hides SDXL anatomy
inconsistency, avoids realistic-person disclosure risk, historical figures stay interpretive);
**cinematic semi-real** only for people-free establishing shots (Visual Director returns
has_people per beat). The DD vector LoRA preset remains selectable (STYLE_PRESETS in
workers/visuals.py). Rationale trade-off noted: richer styles adhere slightly less than the
PAG-vector stack; PAG stays on for all styles.
