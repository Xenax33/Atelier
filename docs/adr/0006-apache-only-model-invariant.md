# 0006 — Every published frame is Apache-2.0 / MIT / OpenRAIL++ / CC-0
Status: Accepted
Date: 2026-07-22

## Context
The channel is monetized. Many popular models/voices are non-commercial or revenue-capped (Flux-dev, SVD,
XTTS/Coqui, F5-TTS, Fish, SD3.5 <$1M, LTX <$10M, some Piper voices). License != output-usage rights, and a
license violation on a monetized channel is a real liability.

## Decision
**Build invariant:** anything whose output appears in a published frame (LLM text, TTS audio, images, video)
must be **Apache-2.0 / MIT / OpenRAIL++ (no cap) / CC-0**. Infra/runtime licenses (AGPL/Elastic/etc.) are fine
as long as they never touch a frame. Maintain the "do-not-use" list in `docs/STACK.md`; per-voice allowlist
for Piper.

## Consequences
- Easy: monetization safety is a compile-time property, not a later audit.
- Hard: rules out some higher-quality NC models (e.g. Flux-dev, XTTS voice cloning of arbitrary voices).
- Revisit when: a model relicenses, or a specific asset gets explicit commercial clearance (record it here).

## Alternatives rejected
- **"Fix licensing later"** — too risky once content is live and earning.
