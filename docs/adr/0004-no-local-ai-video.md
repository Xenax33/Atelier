# 0004 — No local AI video generation on this box; fake motion instead
Status: Accepted
Date: 2026-07-22

## Context
Text-to-video / image-to-video (AnimateDiff, SVD, LTX, Wan, CogVideoX) is the obvious "AI video" instinct,
but RDNA1 has no matrix accel and 8 GB VRAM; every "runs on 8 GB" claim is benchmarked on NVIDIA. Several
of these models are also non-commercial (SVD, Flux-dev, LTX caps).

## Decision
**No generative video.** Motion = **SDXL stills + Depth-Anything-V2 2.5D parallax + Ken-Burns + Manim
diagrams**. This is honest for the hardware and *better* for a science niche — clean animated diagrams beat
hallucinated video.

## Consequences
- Easy: reliable, license-clean, on-cadence renders; diagrams are the niche's real differentiator.
- Hard: no "cinematic AI b-roll"; must invest in Manim/visual-director quality.
- Revisit when: NVIDIA upgrade makes i2v feasible — it becomes a capability-tier feature flag, not a redesign.

## Alternatives rejected
- **AnimateDiff/SVD/Wan on 8 GB AMD** — impractical at a daily cadence; SVD/Flux-dev/LTX also non-commercial.
