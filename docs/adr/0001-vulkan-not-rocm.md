# 0001 - Vulkan/ZLUDA, never ROCm, for the RX 5700 XT
Status: Accepted
Date: 2026-07-22

## Context
The GPU is gfx1010 / RDNA1 (8 GB). In 2026 it has **no official ROCm** (dropped after ROCm 5.2), the old
`HSA_OVERRIDE_GFX_VERSION=10.3.0` shim is dead on torch ≥ 2.0, WSL2/Docker AMD passthrough is unreliable,
and vLLM doesn't target gfx1010. Community ROCm source-builds exist but are fragile and break on version bumps.

## Decision
All GPU inference uses **Vulkan** (llama.cpp, Orpheus) or **ZLUDA** (ComfyUI/SDXL), running as **native
Windows** processes. We do not build anything on ROCm / vLLM / torch-CUDA expectations for this card.

## Consequences
- Easy: reliable local LLM + SDXL on Windows with no dual-boot.
- Hard: no vLLM continuous batching; ~half the tok/s of an RDNA3 card; one heavy GPU stage at a time.
- Revisit when: a **NVIDIA GPU** is installed - then CUDA/vLLM/ROCm all reopen (backend swap via the gateway seam).

## Alternatives rejected
- **ROCm on gfx1010** - unsupported/fragile; silent CPU fallback or broken builds.
- **Linux dual-boot for ROCm** - buys ~10-20% for a card we plan to replace; not worth the maintenance.
- **WSL2 GPU passthrough** - too weak for AMD; GPU servers would run native anyway.
