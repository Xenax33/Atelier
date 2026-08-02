# STACK - pinned choices, why, and the fragile bits

Every **generative/model** pick is monetization-safe by construction (Apache-2.0 / MIT / OpenRAIL++ / CC-0).
Runtime/infra licenses never touch a published frame. Full rationale: `ARCHITECTURE.md` §3.

## Pinned artifacts (verified + downloaded 2026-07-23)

| Artifact | Pinned version | Location | Notes |
|---|---|---|---|
| llama.cpp | **b10092** win-vulkan-x64 | `bin/llama-b10092/` | Vulkan detects the 5700 XT (8176 MiB). Includes the Feb/Mar 2026 AMD FA + graphics-queue fixes. Do NOT swap to Ollama (its vendored llama.cpp lags these fixes by ~56% t/s). |
| **PRIMARY brain** | **Qwen3-4B-Instruct-2507 UD-Q4_K_XL** (2.37 GB, Apache-2.0) | `models/Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf` | **Measured 2026-07-23: 670 tok/s pp512, 93 tok/s tg128 (FA off).** Passed schema-JSON + tool-call smoke clean. Instruct-native, 262k ctx, big VRAM headroom. |
| Fallback brain (A/B) | Qwen3-8B Q4_K_M (4.68 GB, Apache-2.0) | `models/Qwen3-8B-Q4_K_M.gguf` | Measured: 375 pp / 59 tg. FAILED schema-JSON smoke out of the box (hybrid-thinking emits think-tokens; needs chat_template_kwargs plumbing). Keep for quality A/B only. |
| Kokoro TTS | **v1.0 f32 onnx** (310.5 MB) + voices (26.9 MB) | `models/tts/` | **Measured 2026-07-23: 56.3s narration in 20.3s on CPU (2.8x realtime)**, voice af_heart. `scripts/smoke_tts.py`. |
| Python | **3.12.10** + `.venv/` | repo root | 3.12 is the ceiling-safe pick: whisperx + kokoro-onnx require <3.14; manim needs >=3.11. Torch is CPU-only wheels (never CUDA on this box). |
| Visuals engine | **ComfyUI-Zluda** (patientx, master @ 2026-07-25) + HIP SDK 6.2.4 + gfx1010 rocBLAS | `F:\ComfyUI-Zluda` (outside repo: no-spaces path) | **Measured 2026-07-25: 768x1344 SDXL = ~55 min FIRST run (one-time kernel compile), 3.0 min warm.** torch 2.7.0-cu118 + ZLUDA 3.9.5, scipy PINNED ==1.13.1 (numpy 1.26 clash). Venv snapshot: `F:\ComfyUI-Zluda\venv-snapshot-2026-07-25.zip`; freeze: `docs/zluda-venv-freeze-2026-07-25.txt`. Full saga: `docs/SETUP-COMFYUI.md`. |
| Deferred (TASK-008) | Qwen3-30B-A3B-Instruct-2507 UD-Q4_K_XL (17.7 GB) | not downloaded | After the RAM upgrade. Reality check from research: DDR4 caps it at ~12-15 tok/s (the ~30 figure is DDR5-class), so benchmark before re-committing (ADR-0002). |

Notable deviation: captions start with **faster-whisper** (lighter; word timestamps built in). whisperx
(forced alignment) comes in when the captions worker is built, since we align against a KNOWN script.

## Core picks

| Layer | Pick | License (published-frame relevance) |
|---|---|---|
| LLM runtime | **llama.cpp Vulkan server** (prebuilt vulkan release) | MIT (infra) |
| Primary brain (now) | **Qwen3-8B Q4_K_M** fully in VRAM (ADR-0011, 16 GB RAM reality) | **Apache-2.0 -> safe** |
| Primary brain (after RAM upgrade) | **Qwen3-30B-A3B Q4_K_M** `--cpu-moe` (ADR-0002, reinstated by config) | Apache-2.0 -> safe |
| Structured output | GBNF / JSON-schema constrained decoding | technique |
| Model gateway | **LiteLLM proxy** or ~150-line FastAPI facade | MIT (infra) |
| TTS default | **Kokoro-82M** via `kokoro-onnx` (CPU) | **Apache-2.0 -> safe** |
| TTS emotive (opt) | Orpheus-3B GGUF via llama.cpp Vulkan + SNAC | Apache-2.0 -> safe |
| TTS signature (opt) | Chatterbox-Turbo (CPU) - **your own consented voice only** | MIT engine (identity ≠ licensed) |
| Image | **SDXL 1.0 base** + style LoRAs (ComfyUI-Zluda) | **OpenRAIL++-M, no revenue cap -> safe** |
| Hero-frame (opt) | Flux.1 **schnell** GGUF | Apache-2.0 -> safe (**never Flux.1 dev**) |
| Depth/parallax | Depth-Anything-V2 | Apache-2.0 |
| Motion graphics | **Manim CE** (+ matplotlib) | MIT/BSD |
| Captions | **faster-whisper** (whisperX forced alignment planned) | MIT/BSD-2 |
| Assembly | **MoviePy + ffmpeg** (1080×1920 H.264) | MIT/LGPL |
| Orchestration | **LangGraph MIT core** + `SqliteSaver` | **MIT** (never langgraph-api/Platform - Elastic) |
| Discord | **discord.py 2.6.x** | MIT |
| Embeddings | **bge-m3** / bge-small-en-v1.5 (CPU) | MIT |
| Vector/dedup | **sqlite-vec** -> **pgvector** | MIT/PostgreSQL |
| Observability | **OpenLLMetry -> Phoenix** -> Langfuse (v2) | Apache/ELv2/MIT |
| Preview delivery | Caddy/nginx + Cloudflare Tunnel | Apache/BSD |
| Publishing | google-api-python-client (private draft) | Apache-2.0 |
| Secrets | SOPS + age | MPL/Apache |

## ⛔ Downloadable-but-DO-NOT-USE (monetization traps)

Flux.1 **dev**, **Stable Video Diffusion**, **F5-TTS** (CC-BY-NC), **Coqui/XTTS v2** (CPML NC) ,
**Fish OpenAudio** (research), **SD3.5** (<$1M cap), **LTX-Video** (<$10M cap), **Piper voices** with
NC/research licenses (engine is fine - audit each *voice*). Infra to avoid if "fully OSS" is strict:
**LangGraph Platform** (Elastic), **n8n** (fair-code).

## GPU model servers are installed SEPARATELY (not pip)

1. **llama.cpp** - download a prebuilt **Vulkan** release; run `llama-server` with `--cpu-moe`.
2. **ComfyUI-Zluda** - native Windows fork; the fragile one (see below).

## ⚠️ The ComfyUI-Zluda fragility (TASK-002) - SNAPSHOT THE VENV

ZLUDA + Triton + a gfx1010-patched flash-attn wheel is a house of cards that breaks on version bumps.

- Pin **Triton 3.0.0** and the specific gfx1010 flash-attn wheel that works.
- **The moment it generates one image, snapshot the venv** (zip `.venv` or `pip freeze > zluda-freeze.txt`),
  and record the exact wheel URLs here.
- Store the snapshot outside git (it's large) but document its location + restore steps in `RUNBOOK.md`.
- If Phase-0 ZLUDA setup exceeds ~1 day, ship MVP with **Manim + gradient title cards + Pexels b-roll** and
  add SDXL later (Risk R3).

### Working ZLUDA recipe (fill in during TASK-002)
```
# Triton: 3.0.0
# flash-attn (gfx1010) wheel: <URL>
# ComfyUI-Zluda commit: <sha>
# snapshot location: <path>
```
