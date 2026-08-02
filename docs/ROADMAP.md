# Roadmap

High-level direction. The **authoritative, granular** task list is [`tasks/ledger.jsonl`](../tasks/ledger.jsonl);
the full rationale is [`docs/ARCHITECTURE.md` §6](ARCHITECTURE.md). Each phase has a testable Definition of Done.

| Phase | Goal | Status |
|---|---|---|
| **0 - Skeleton** | One command boots the whole stack green: llama.cpp Vulkan brain, ComfyUI-Zluda SDXL, Kokoro TTS, a Discord bot with a working button. | 🟢 Done (2026-07-25, all measured) |
| **MVP** | A topic becomes a finished 9:16 short (VO + burned captions + SDXL stills) through three Discord gates, **resumable across a PC restart**. Manual upload by the owner. | 🟢 Done (2026-07-25) |
| **v1** | The credibility + intelligence layer: ideation-first /ideas + SearXNG, evidence-grounded scripts, **mandatory fact-checker** with mechanical citation resolution, 3-candidate scripts + Editor ranking, vector dedup memory, taste-signal capture. | 🟢 Core done (2026-07-27); in progress: archival visuals (TASK-020), research depth (TASK-021) |
| **v2** | Hardening + extension: containerize the CPU plane (full docker becomes possible post-NVIDIA), extract the render worker, optional Instagram, an eval loop on retention, optional signature voice / MCP tools / Temporal. | ⚪ Not started |

### Guiding constraints (see ADRs)
- Runs fully local on AMD **RX 5700 XT (gfx1010, 8 GB)** via **Vulkan/ZLUDA**, Windows-native. No paid cloud in the core loop.
- Every **published frame** stays monetization-license-clean (Apache/MIT/OpenRAIL++/CC-0).
- Human approval gates + fact-checking are load-bearing, not optional.
- Built along three seams so an **NVIDIA upgrade** (which unlocks local AI video + big speedups) is a backend swap, not a rewrite.

Ideas and feature requests are welcome via [issues](https://github.com/Xenax33/Atelier/issues).
