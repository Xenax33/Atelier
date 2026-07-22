# HARDWARE — the constraints that shape every design choice

## The box

| Part | Spec | Implication |
|---|---|---|
| CPU | AMD Ryzen 5 5600 (6c/12t) | Fine for CPU inference of small models, TTS, Manim, embeddings. |
| RAM | 64 GB DDR4 | **The real asset.** Enables MoE `--cpu-moe` expert offload + CPU-side TTS/diagram/embeddings. |
| GPU | **AMD RX 5700 XT — gfx1010 / RDNA1, 8 GB VRAM** | The governing constraint. See below. |
| Board | MSI B450M | — |
| OS | Windows 11 | Runtime is **Windows-native** (ADR-0007). |

Future: an **NVIDIA upgrade** is planned "if this works." It's the highest-leverage change in the project
(unlocks local AI video + vLLM/ROCm + big speedups) and is a **backend swap, not a redesign** thanks to the
model-gateway seam. Until then, everything below holds.

## The gfx1010 / RDNA1 truths (do not relearn these the hard way)

- **No official ROCm in 2026.** Support was dropped after ROCm 5.2 and never restored for RDNA1.
- **The `HSA_OVERRIDE_GFX_VERSION=10.3.0` shim is dead** on torch ≥ 2.0 (segfaults). Do not rely on it.
- **No fast FP16/WMMA matrix cores.** Benchmarks from RDNA3 (7900-class) cards do **not** transfer — expect
  roughly half the tok/s. Prompt-processing (prefill) on long contexts feels slow.
- **No reliable Docker/WSL2 GPU passthrough** for AMD on Windows. GPU servers must run **native**.
- **Only two reliable GPU paths:** **Vulkan** (llama.cpp, Orpheus) and **ZLUDA** (ComfyUI/SDXL).
- **vLLM is off the table** (targets CDNA/RDNA3, not gfx1010).

➡️ **Never** build on ROCm / vLLM / torch-CUDA-expectations for this card. (ADR-0001)

## The one rule that governs the whole pipeline: 8 GB holds ONE heavy GPU stage at a time

The `--cpu-moe` brain (Qwen3-30B-A3B) uses only **~2 GB VRAM** (experts live in system RAM), so **text
reasoning can overlap with anything**. But the heavy GPU stages must be **serialized** — never co-resident:

- **SDXL image generation** (ComfyUI-Zluda)
- **GPU whisper** (captioning, if run on GPU instead of CPU)
- **Orpheus TTS** (if you use the emotive GPU voice instead of CPU Kokoro)

The workflow owns stage ordering and explicit unloads. **Health-gate before every GPU step.** If two heavy
models are ever resident at once → OOM. (Risk R2.)

## Rough performance expectations on this box

| Workload | Expectation |
|---|---|
| Qwen3-30B-A3B Q4 `--cpu-moe` | ~30 tok/s, ~2 GB VRAM (rest in RAM) |
| Qwen3-8B Q4 (in VRAM) | ~45–55 tok/s |
| Kokoro TTS (CPU) | ~5–15× realtime (60 s clip in seconds) |
| SDXL 768×1344 (ZLUDA, --lowvram) | ~1–5 min / image |
| whisperX (CPU) | comfortably realtime-ish for a 60 s clip |
| AI video (t2v/i2v) | **not feasible at a daily cadence — don't** (ADR-0004) |

## VRAM budget cheat-sheet

```
8 GB total
├─ ~2 GB   Qwen3-30B-A3B (--cpu-moe, shared+attention weights)   ← always resident
└─ ~6 GB   free for the ONE active heavy stage (SDXL | GPU-whisper | Orpheus)  ← serialize these
```
