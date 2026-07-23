# 0002 - Qwen3-30B-A3B via llama.cpp `--cpu-moe` as the primary brain
Status: Superseded by 0011 (reinstate after the RAM upgrade to 64 GB, see TASK-008)
Date: 2026-07-22

## Context
8 GB VRAM can't hold a dense 30B model, and dense 7-8B models are unreliable as autonomous agent brains
(malformed tool-JSON, hallucinated calls). But we have 64 GB system RAM.
_(2026-07-23 correction: the audit found 16 GB, not 64. See ADR-0011. This ADR becomes the target state
again once the RAM upgrade lands.)_

## Decision
Run **Qwen3-30B-A3B Q4_K_M** (MoE: 30B total, ~3.3B active) via **llama.cpp Vulkan** with **`--cpu-moe`**,
parking experts in system RAM. Uses ~**2 GB VRAM**, ~30 tok/s, with 30B-class reasoning + reliable
tool-calling. Keep **Qwen3-8B Q4** (fully in VRAM, ~45-55 tok/s) as a fast lane for routing/tagging.
Enforce reliable JSON via **GBNF/JSON-schema constrained decoding**.

## Consequences
- Easy: big-brain quality + tool-calling on an 8 GB card; brain stays resident and never fights SDXL for VRAM.
- Hard: ~30 tok/s (fine for on-demand daily runs, not interactive chat); prefill on long research contexts is slow.
- Revisit when: NVIDIA upgrade (larger/faster models, longer context).

## Alternatives rejected
- **Dense 13-14B in VRAM** - barely fits, no room for KV cache, weaker tool-calling than 30B-A3B.
- **7-8B as the main agent brain** - unreliable for multi-step orchestration.
- **Apache-2.0 requirement** keeps outputs monetization-clean (see ADR-0006); rules out some Llama/Mistral options.
