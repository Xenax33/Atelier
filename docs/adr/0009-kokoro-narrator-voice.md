# 0009 — Kokoro neutral preset as the default narrator voice
Status: Accepted
Date: 2026-07-22
_User decision (2026-07-22): "Kokoro neutral preset"._

## Context
Voice options: Kokoro neutral preset (CPU), Orpheus emotive (GPU), or a Chatterbox clone of the user's own
voice. Voice cloning of third parties is a right-of-publicity risk regardless of model license.

## Decision
Default to **Kokoro-82M preset voices via `kokoro-onnx` on CPU** (Apache-2.0). Zero likeness/legal risk, zero
GPU contention, seconds per clip. Orpheus (emotive, Vulkan) and Chatterbox (own-voice-only) remain optional
upgrades behind the TTS worker interface.

## Consequences
- Easy: clean explainer VO, no GPU serialization cost, no consent/identity concerns.
- Hard: less vocal personality than emotive/cloned options.
- Revisit when: the channel wants a signature narrator → add Orpheus, or clone the user's **own consented** voice.

## Alternatives rejected
- **Third-party voice cloning** — impersonation / right-of-publicity risk (ADR-0006 spirit, Risk R8).
