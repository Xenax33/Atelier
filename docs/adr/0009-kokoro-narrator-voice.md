# 0009 - Kokoro neutral preset as the default narrator voice
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
- Revisit when: the channel wants a signature narrator -> add Orpheus, or clone the user's **own consented** voice.

## Alternatives rejected
- **Third-party voice cloning** - impersonation / right-of-publicity risk (ADR-0006 spirit, Risk R8).

## Amendment (2026-08-03): Orpheus is REJECTED on license, not deferred on hardware
Verified at the source (HF discussion #4 on canopylabs/orpheus-3b-0.1-pretrained): Orpheus-3B is a
Llama-3.2-3B finetune tagged Apache-2.0; the conflict was reported June 2025 and Canopy never
responded. Effective license is the Llama 3.2 Community License - off the ADR-0006 allowlist - and
TTS output is audible frame content on a monetized channel. Revisit only if retrained on a clean base.
Replacement upgrade path (license-verified 2026-08-03): **NeuTTS Air** (Apache-2.0, Qwen-0.5B
backbone, official Q4/Q8 GGUFs, realtime CPU, own-voice cloning from 3-15s) as the signature-voice
primary; **Chatterbox-Nano** (MIT, 110M, Perth-watermarked output) runner-up; **Maya1** (Apache-2.0,
from-scratch 3B) the post-NVIDIA expressive option. Own recorded voice only (R8 stands).
Also 2026-08-03: synthesis is per-segment with explicit gaps (exact beat timestamps for assembly),
the Kokoro model is a process singleton, speed default 1.05, and output runs through an ffmpeg
voice chain (highpass/de-ess/compress/-16 LUFS) - see docs/research/2026-08-03-pipeline-rnd.md 5.2/5.3.
