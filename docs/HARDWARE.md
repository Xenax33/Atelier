# HARDWARE - the constraints that shape every design choice

## The box (verified by audit, 2026-07-23)

| Part | Spec | Implication |
|---|---|---|
| CPU | AMD Ryzen 5 5600 (6c/12t) | Fine for CPU inference of small models, TTS, Manim, embeddings. |
| RAM | **16 GB DDR4-3200 (2x8 GB, both slots filled)** | The original plan assumed 64 GB; audit found 16. This defers the MoE `--cpu-moe` brain (ADR-0011). Board max is 128 GB, so a 2x32 GB swap reinstates it. |
| GPU | **AMD RX 5700 XT - gfx1010 / RDNA1, 8 GB VRAM** | The governing constraint. See below. |
| Board | MSI B450M (2 DIMM slots) | RAM upgrade = replace both sticks. |
| OS | Windows 11 | Runtime is **Windows-native** (ADR-0007). Driver: Adrenalin 2026-06, Vulkan runtime present. |
| Disk | F: ~205 GB free | Models + renders live here. |
| Python | 3.12.10 installed | App layer target. |

Two planned upgrades, in order of leverage per dollar:
1. **RAM to 2x32 GB DDR4-3200** - cheap-ish (DDR4 pricing is volatile, check current), unlocks the
   Qwen3-30B-A3B `--cpu-moe` brain (ADR-0002 reinstated by config, no code change).
2. **NVIDIA GPU** - the big one: local AI video, vLLM/CUDA, big speedups. A backend swap, not a redesign,
   thanks to the model-gateway seam.

## The gfx1010 / RDNA1 truths (do not relearn these the hard way)

- **No official ROCm in 2026.** Support was dropped after ROCm 5.2 and never restored for RDNA1.
- **The `HSA_OVERRIDE_GFX_VERSION=10.3.0` shim is dead** on torch >= 2.0 (segfaults). Do not rely on it.
- **No fast FP16/WMMA matrix cores.** Benchmarks from RDNA3 (7900-class) cards do **not** transfer - expect
  roughly half the tok/s. Prompt-processing (prefill) on long contexts feels slow.
- **No reliable Docker/WSL2 GPU passthrough** for AMD on Windows. GPU servers must run **native**.
- **Only two reliable GPU paths:** **Vulkan** (llama.cpp, Orpheus) and **ZLUDA** (ComfyUI/SDXL).
- **vLLM is off the table** (targets CDNA/RDNA3, not gfx1010).

**Never** build on ROCm / vLLM / torch-CUDA-expectations for this card. (ADR-0001)

## The one rule that governs the whole pipeline: 8 GB holds ONE heavy GPU stage at a time

Until the RAM upgrade, the primary brain is **dense Qwen3-8B fully in VRAM (~5-6 GB with KV cache)**, which
makes the LLM itself a heavy GPU stage. The heavy stages must be **serialized** - never co-resident:

- **The 8B brain** (llama.cpp Vulkan server)
- **SDXL image generation** (ComfyUI-Zluda)
- **GPU whisper** (captioning, if run on GPU instead of CPU)
- **Orpheus TTS** (if you use the emotive GPU voice instead of CPU Kokoro)

In practice this is painless because the pipeline is naturally phased per short: all LLM work (research,
scripts, fact-check, visual prompts) completes BEFORE rendering starts. The graph stops or idles the
llama-server before launching a ComfyUI render and restarts it after (an 8B reload takes seconds).
**Health-gate before every GPU step.** If two heavy models are ever resident at once -> OOM. (Risk R2.)

After the RAM upgrade, the 30B MoE brain drops VRAM use to ~2 GB (experts in RAM) and can stay resident
through renders; the serialization rule then only covers SDXL / GPU-whisper / Orpheus. (ADR-0002)

## Rough performance expectations on this box

| Workload | Expectation |
|---|---|
| Qwen3-8B Q4 (in VRAM) - PRIMARY for now | ~45-55 tok/s |
| Qwen3-30B-A3B Q4 `--cpu-moe` - AFTER RAM upgrade | ~2 GB VRAM; tok/s TBD on DDR4 (benchmark then) |
| Kokoro TTS (CPU) | ~5-15x realtime (60 s clip in seconds) |
| SDXL 768x1344 (ZLUDA, --lowvram) | ~1-5 min / image |
| whisperX (CPU) | comfortably realtime-ish for a 60 s clip |
| AI video (t2v/i2v) | **not feasible at a daily cadence - don't** (ADR-0004) |

## VRAM budget cheat-sheet (current, pre-RAM-upgrade)

```
8 GB total
+- ~5-6 GB  Qwen3-8B Q4 + KV cache   <- while text stages run
+- ~6-7 GB  SDXL (--lowvram)         <- while rendering (brain stopped)
ONE heavy occupant at a time. The graph owns the ordering.
```

RAM budget matters too now: 16 GB total, ~8 GB free with the desktop running. Keep the app layer lean;
close heavy apps (browser tabs, games) before a pipeline run. Track RAM in the health checks.
