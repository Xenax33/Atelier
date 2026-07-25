# Changelog

Notable changes, newest first. Keep entries short; link tasks (`TASK-###`) and ADRs where relevant.

## 2026-07-25 - The visuals engine is alive: Phase 0 complete (TASK-002 done)
- **First SDXL images rendered on the RX 5700 XT via ZLUDA**: 768x1344 flat-vector style, clean output.
  First-ever run ~55 min (one-time ZLUDA/MIOpen kernel compile), **3.0 min per image warm**.
- Stack: ComfyUI-Zluda (patientx) + HIP SDK 6.2.4 + community gfx1010 rocBLAS + ZLUDA 3.9.5,
  torch 2.7.0-cu118 patched. Traps documented in docs/SETUP-COMFYUI.md (wrong-SDK-version page,
  Defender-locked zluda.zip, scipy/numpy clash). Venv snapshotted.
- `scripts/smoke_sdxl.py` added (API-driven render smoke with timing + seed control).
- `start-day.ps1`: ComfyUI now opt-in via `-WithComfy` (VRAM serialization rule); brain+bot by default.
- **Phase 0 is complete**: brain, voice, visuals, control plane - all measured on this exact box.

## 2026-07-25 - The control plane is live (TASK-004 done)
- Discord bot **Atelier#1371** running: guilds-only intents, guild-scoped slash sync, `/status` stack
  health, boot announcement card with persistent **Ping bot** / **Check brain** buttons.
- **Restart test passed**: a button on a card posted before a bot restart still worked after relaunch.
  Persistent views are the foundation the approval gates will be built on.
- New: `src/config.py` (pydantic-settings), `src/bot/{client,views}.py`, `src/main.py`; start-day.ps1
  now launches the app when .env is configured.

## 2026-07-23 - The brain and the voice are up (TASK-001, TASK-003 done)
- llama.cpp **b10092 Vulkan** installed; detects the RX 5700 XT cleanly. Benchmarked on-card:
  **Qwen3-4B-Instruct-2507** chosen as primary brain (670 pp / **93 tok/s** tg, schema-JSON + tool-calls
  pass); Qwen3-8B kept as A/B fallback (375/59, failed schema-JSON via thinking tokens). FA off on RDNA1.
- **Kokoro TTS** measured: 56.3s narration in 20.3s on CPU (2.8x realtime). `scripts/smoke_tts.py`.
- Python 3.12 venv built: CPU torch 2.8, discord.py 2.7.1, langgraph, kokoro-onnx, moviepy, manim,
  sentence-transformers, sqlite-vec, faster-whisper. Smoke scripts added under `scripts/`.
- `start-day.ps1` now really boots + health-gates the llama gateway.

## 2026-07-23 - Hardware audit + Phase 0 start
- Hardware audit corrected a core assumption: the box has **16 GB RAM (2x8)**, not 64 GB. ADR-0011 added:
  primary brain is now **Qwen3-8B in VRAM**; the 30B `--cpu-moe` plan (ADR-0002) is deferred behind a
  2x32 GB RAM upgrade (TASK-008). HARDWARE/STACK/CONTEXT/.env.example updated to match.
- TASK-001 started: llama.cpp Vulkan server + pinned-artifact research before any downloads.
- SECURITY.md: supported branch is `master` (repo pushed to github.com/Xenax33/Atelier).

## 2026-07-22 - Project bootstrap
- Repo scaffolded; context-handoff system initialized (`CONTEXT.md`, `docs/`, `docs/adr/`, `tasks/ledger.jsonl`).
- Full architecture captured in `docs/ARCHITECTURE.md` (from a 12-agent research + design pass).
- Locked initial decisions via ADRs 0001-0010 (Vulkan-not-ROCm, `--cpu-moe` 30B brain, LangGraph+SQLite spine,
  no local AI video, private-draft publish, Apache-only model invariant, Windows-native runtime, flat-vector
  visual style, Kokoro narrator, editorial taste model).
- Phase 0 tasks seeded in `tasks/ledger.jsonl`.
- Open-sourced under **MIT**: added `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `docs/ROADMAP.md`, GitHub issue/PR templates, a `ruff` CI workflow, `pyproject.toml`, `.gitattributes`,
  and `.editorconfig`. README updated with badges + disclaimer. Public repo: `Xenax33/Atelier`.
