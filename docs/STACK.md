# STACK — pinned choices, why, and the fragile bits

Every **generative/model** pick is monetization-safe by construction (Apache-2.0 / MIT / OpenRAIL++ / CC-0).
Runtime/infra licenses never touch a published frame. Full rationale: `ARCHITECTURE.md` §3.

## Core picks

| Layer | Pick | License (published-frame relevance) |
|---|---|---|
| LLM runtime | **llama.cpp Vulkan server** (prebuilt vulkan release) | MIT (infra) |
| Primary brain | **Qwen3-30B-A3B Q4_K_M** `--cpu-moe` | **Apache-2.0 → safe** |
| Fast-lane brain | **Qwen3-8B Q4_K_M** (in VRAM) | Apache-2.0 → safe |
| Structured output | GBNF / JSON-schema constrained decoding | technique |
| Model gateway | **LiteLLM proxy** or ~150-line FastAPI facade | MIT (infra) |
| TTS default | **Kokoro-82M** via `kokoro-onnx` (CPU) | **Apache-2.0 → safe** |
| TTS emotive (opt) | Orpheus-3B GGUF via llama.cpp Vulkan + SNAC | Apache-2.0 → safe |
| TTS signature (opt) | Chatterbox-Turbo (CPU) — **your own consented voice only** | MIT engine (identity ≠ licensed) |
| Image | **SDXL 1.0 base** + style LoRAs (ComfyUI-Zluda) | **OpenRAIL++-M, no revenue cap → safe** |
| Hero-frame (opt) | Flux.1 **schnell** GGUF | Apache-2.0 → safe (**never Flux.1 dev**) |
| Depth/parallax | Depth-Anything-V2 | Apache-2.0 |
| Motion graphics | **Manim CE** (+ matplotlib) | MIT/BSD |
| Captions | **whisperX** / faster-whisper | BSD-2/MIT |
| Assembly | **MoviePy + ffmpeg** (1080×1920 H.264) | MIT/LGPL |
| Orchestration | **LangGraph MIT core** + `SqliteSaver` | **MIT** (never langgraph-api/Platform — Elastic) |
| Discord | **discord.py 2.6.x** | MIT |
| Embeddings | **bge-m3** / bge-small-en-v1.5 (CPU) | MIT |
| Vector/dedup | **sqlite-vec** → **pgvector** | MIT/PostgreSQL |
| Observability | **OpenLLMetry → Phoenix** → Langfuse (v2) | Apache/ELv2/MIT |
| Preview delivery | Caddy/nginx + Cloudflare Tunnel | Apache/BSD |
| Publishing | google-api-python-client (private draft) | Apache-2.0 |
| Secrets | SOPS + age | MPL/Apache |

## ⛔ Downloadable-but-DO-NOT-USE (monetization traps)

Flux.1 **dev** · **Stable Video Diffusion** · **F5-TTS** (CC-BY-NC) · **Coqui/XTTS v2** (CPML NC) ·
**Fish OpenAudio** (research) · **SD3.5** (<$1M cap) · **LTX-Video** (<$10M cap) · **Piper voices** with
NC/research licenses (engine is fine — audit each *voice*). Infra to avoid if "fully OSS" is strict:
**LangGraph Platform** (Elastic), **n8n** (fair-code).

## GPU model servers are installed SEPARATELY (not pip)

1. **llama.cpp** — download a prebuilt **Vulkan** release; run `llama-server` with `--cpu-moe`.
2. **ComfyUI-Zluda** — native Windows fork; the fragile one (see below).

## ⚠️ The ComfyUI-Zluda fragility (TASK-002) — SNAPSHOT THE VENV

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
