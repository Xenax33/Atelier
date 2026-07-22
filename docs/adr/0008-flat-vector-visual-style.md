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
