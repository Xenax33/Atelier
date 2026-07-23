# 0011 - 16 GB RAM reality: Qwen3-8B primary brain until the RAM upgrade
Status: Accepted
Date: 2026-07-23
_User decision (2026-07-23): "Start with 8B now, upgrade RAM later."_

## Context
A hardware audit (2026-07-23) found the box has **2x8 GB = 16 GB DDR4**, not the 64 GB that ADR-0002
assumed. The board (MSI B450M) has only 2 DIMM slots, both filled; max capacity 128 GB. Qwen3-30B-A3B
Q4_K_M is ~18.6 GB and `--cpu-moe` needs ~17 GB of experts resident in system RAM: on 16 GB it would page
off SSD and be unusably slow. This is a fact conflict with ADR-0002, not a tuning problem.

## Decision
1. **Primary brain now: dense Qwen3-8B Q4_K_M fully in VRAM** (~5 GB weights + KV, ~45-55 tok/s) served by
   llama.cpp Vulkan behind the model gateway.
2. **Compensate for 8B agent weakness structurally, not hopefully:**
   - GBNF/JSON-schema constrained decoding is mandatory on every structured output.
   - The graph owns control flow; agents get single-tool, single-step prompts with tight schemas.
     Never ask the 8B to plan multi-step tool chains on its own.
   - The fact-checker and human gates stay load-bearing (they were designed for exactly this).
3. **RAM upgrade path tracked as TASK-008** (2x32 GB DDR4-3200, replaces both sticks). After the upgrade,
   ADR-0002 is reinstated by config: point the gateway at the 30B `--cpu-moe` server. No code change.

## Consequences
- Easy: Phase 0 proceeds today at zero cost; the 8B is fast (~45-55 tok/s) and fits VRAM whole.
- Hard: the brain now occupies ~5-6 GB VRAM, so it is itself a heavy GPU stage. The brain and SDXL must be
  serialized (stop llama-server during renders; reload takes seconds). See HARDWARE.md.
- Hard: weaker reasoning on long research synthesis; keep agent steps small and schema-bound.
- Revisit when: RAM upgrade lands (reinstate ADR-0002) or NVIDIA upgrade lands (bigger brains entirely).

## Benchmark outcome (2026-07-23, llama.cpp b10092 Vulkan, on-card)
The planned "Qwen3-8B" slot went to **Qwen3-4B-Instruct-2507 (UD-Q4_K_XL)** on measured data:
- 4B-Instruct-2507: 670 tok/s pp512, **93 tok/s tg128**, passed schema-JSON + tool-call smoke clean.
- Qwen3-8B Q4_K_M: 375 pp512, 59 tg128, and **failed the schema-JSON smoke** (hybrid-thinking model
  emits think-tokens into the constrained output without extra chat-template plumbing).
- The 2507 instruct recipe benchmarks at or above the original 8B non-thinking mode, is instruct-native,
  has 262k native context, and leaves ~5 GB VRAM headroom. The 8B stays on disk for quality A/B tests.
- Flash attention on RDNA1: works but costs ~15% prompt speed, so it stays off (f16 KV, we have room).

## Alternatives rejected
- **2-bit quant of the 30B MoE (~10-11 GB)** - might physically fit, but tool-call/JSON reliability
  degrades hard at 2-bit and this brain drives a structured pipeline. Wrong trade.
- **gpt-oss-20b MoE (~12 GB, Apache-2.0)** - still does not fit 16 GB RAM alongside OS + app stack, and
  its harmony/reasoning format is a poor fit for schema-driven agent steps on this stack.
- **Buy RAM first, build later** - blocks Phase 0 on a delivery for no technical gain; the gateway seam
  makes the later swap trivial anyway.
