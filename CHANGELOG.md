# Changelog

Notable changes, newest first. Keep entries short; link tasks (`TASK-###`) and ADRs where relevant.

## 2026-08-08 - True-60s word budgets + Gemma 4 E4B cleared for A/B (TASK-038)
- **Under-60s videos diagnosed as a budget bug, not a model failure**: measured 2.90 spoken
  words/sec means the old 130-155-word target produced 48-56s shorts. New target 160-175
  (accept 150-190), beats ask 2-3 evidence-grounded sentences - length now buys detail.
- **Gemma 4 E4B: license objection RESOLVED** - Gemma 4 (April 2026) is Apache 2.0; the old
  Gemma Terms explicitly exclude it, so the TASK-012-era rejection applied to Gemma 3-class only.
  Benchmarked on this box: loads clean on Vulkan/gfx1010, 42-51 tok/s, schema-JSON and tool
  smoke pass, ~2x word-count adherence and detail density vs Qwen3-4B in identical probes.
  Caveats logged (PLE wiring issue #22243, weaker tool calling). The 12B download is incomplete
  and would not fit 8 GB - skipped.
- **Brain is now config-swappable**: BRAIN_MODEL_PATH in .env drives config.py, the render
  worker's llama restarts, gateway self-healing, and start-day.ps1. Default stays Qwen3-4B;
  the A/B is one .env line + one production run judged at Gate 1.

## 2026-08-08 - A/B session: AYS-12 + per-style checkpoints adopted, hires rejected (TASK-037)
- Same-seed matrix (8 renders + 2 combo verifications, timed): **AYS 12-step adopted** (2.6x
  faster, 118s vs ~315s, quality on par; 10 steps flatter - stays 12); **DreamShaper XL 1.0**
  is the painterly checkpoint (painted light vs flat outlines) and **RealVisXL V5.0** the
  cinematic one (photographic depth) - both verified as a combined stack with AYS + PAG.
- **Hires-fix rejected as-shipped** (frame-wide smearing on this ZLUDA stack); flag stays off
  with retune notes. ADR-0008 amended. Warm render cost per beat is now ~2.1 min, was ~5.3.
- Prep work: DreamShaper converted from diffusers shards to a verified single-file checkpoint;
  installed guidance-alternative node ids documented (core PAG vs pack's PerturbedAttention).

## 2026-08-06 - The studio never auto-starts after a reboot (TASK-036)
- **Owner demand**: no more self-starting after reboots/power cuts. `state\.studio-on` is now
  boot-session-scoped: start-day stamps it with the current boot id, the watchdog honors it only
  while that boot id matches, and a stale marker is deleted on sight. `./start-day.ps1` is the
  single manual command that starts the studio; within-session crash healing is unchanged.
  Verified live (stale marker -> deleted, nothing started). Marker/lock/log files untracked.
- Laptop patch TASK-032..035 applied: 14 files clean, 3 hand-merged with the 2026-08-04 studio-box
  work (render-lock mutex, resume-reuse, abs paths, per-preset ckpt). Full validation matrix green.

## 2026-08-06 - Cut-ins, script-text captions, dark render flags, ops batch (TASK-035)
- **Cut-ins (ON)**: segments >=6s get a second shot - an upper-biased 62% crop-reframe of the
  same approved still - halving the visual-change interval for free (R&D 7.1). Archival
  letterboxed frames excluded. Found+fixed while in there: Ken-Burns scale was hardcoded to
  768x1344, over-zooming 1080x1920 archival frames 1.4x and cropping the letterbox.
- **Script-text captions (ON)**: words.json now carries the SCRIPT's spelling on whisper's
  timings (difflib alignment; ASR hallucinations dropped, missed words squeeze into gaps);
  raw ASR kept in words_asr.json. Kills caption misspellings of science terms (R&D 7.3).
- **Dark flags in visuals.py** (ship OFF; same-seed A/B one at a time per R&D 7.8): USE_AYS
  (12-step Align-Your-Steps first pass), USE_HIRES (1.5x latent second pass + tiled VAE),
  KEEP_COMFY_WARM (`POST /free` + VRAM gate instead of process kill). Node signatures
  verified against upstream ComfyUI source. SEG/FDG/NAG guidance flag deliberately NOT
  shipped: the pack's node names differ between installed version and master - identify
  them in the local ComfyUI UI first (10-min studio-box task).
- **Ops**: master.mp4 now carries bt709 color tags (R&D 7.4); `scripts/snapshot-caches.ps1`
  snapshots/restores the ZLUDA/MIOpen/triton kernel caches (RUNBOOK section added).
- Deferred from R&D 6.4: the overnight seed sweep (needs graph/bot integration + on-box test).

## 2026-08-06 - Research-layer upgrades: primary sources, Wikidata year check, typed hooks (TASK-034)
- **Primary-source adapters** (R&D 4.6, `tools/research.py`): Chronicling America via the loc.gov
  JSON API (the legacy API died in 2025), Open Library book records, NASA ADS (dormant until the
  free `ADS_API_TOKEN` is set in .env - see .env.example). Evidence pack reordered wikipedia ->
  primary -> papers -> web with cap 10->14, so the cap trims searxng snippets, never the
  DOI-bearing papers. Open Library + Wikidata live-tested; **loc.gov 403'd the dev network -
  verify from the studio box once** (fail-soft: returns [] until then).
- **Wikidata year cross-check** (R&D 4.5): deterministic, advisory-only off-by-1/2 date flags
  (birth/death/discovery, CC0, keyless) against entities already identified upstream; they surface
  as `uncertain` claims on the existing Gate 1 card - zero bot changes. Live-tested: flags
  1846-vs-1845 for Röntgen, stays silent on exact matches.
- **Typed hooks + word budgets in code** (R&D 4.8): `hook_type` enum in the spec schema (Editor
  now sees and critiques the type; feeds taste consolidation), and `_budget_violations()` enforces
  hook <=12 words / beat 8-45 / total 110-170 with the existing one-retry pattern. Hook budget
  deliberately stays at the current editorial 12 words (the report's 7-word sub-2s option is an
  owner decision - see report 4.8 correction on the pacing math).

## 2026-08-06 - Audio review fixes + off-topic-image / missing-archival diagnosis (TASK-032/033)
- **Review fixes on the TASK-030 batch**: `deesser` ran at its default intensity 0 (a verified
  pass-through - it de-essed nothing), now `i=0.35`; voice chain gains the 0.3s `apad` tail
  (R&D 5.3); ASS timestamps use integer centisecond math (float rounding could emit a malformed
  `0:00:60.00`). Music-duck filtergraph verified legal end-to-end on synthetic audio, but it has
  never run with a real track (assets/music/ is empty) - test once after adding a track.
- **Off-topic images diagnosed** (user report: image subjects unrelated to the script): Visual
  Director schema now forces EXACTLY one prompt per beat (minItems=1 allowed fewer -> the pad
  silently shifted prompts onto wrong beats); system prompt gains a literal-first rule and
  metaphors must reuse a concrete noun from the narration; an empty prompt can no longer reach
  SDXL as a style-only "vacuum" render (topic-anchored fallback).
- **Missing archival images diagnosed** (user report: none used despite the feature): the visuals
  node overwrote `visual_prompt` with the Director's metaphor BEFORE CLIP scoring, so real
  archival photos scored near-zero against metaphors and fell under the 0.28 threshold ->
  silent SDXL fallback. Scoring now uses the writer's literal prompt (as calibrated), and every
  per-beat decision/error lands in `assets/visual_plan.json` (both `except: pass` blocks now
  leave a trace). **Verify on the studio box next run** - read visual_plan.json first.

## 2026-08-03 - R&D sweep verified + weekend batch: sync, karaoke captions, sound (TASK-030)
- **Pipeline R&D sweep verified** (docs/research/2026-08-03-pipeline-rnd.md + its section 9 addendum):
  license claims re-checked at primary sources; three corrections (Orpheus ban stands on Meta's terms,
  Qwen3.5 thinking is ON by default - gate any swap on the schema smoke test, AYS is ~20-step quality).
- **Beat-synced cuts**: TTS now synthesizes per segment (hook/beats/outro) with explicit gaps and writes
  `beat_timing.json`; assembly cuts on real narration boundaries instead of word-count proportions.
- **Karaoke captions**: ASS/libass with per-word `\kf` sweep, burned by ffmpeg with the in-repo OFL
  Archivo Black font (assets/fonts/). Replaces MoviePy TextClips (and the old clipping workaround);
  Shorts-safe margins (block above y=1540, right rail cleared).
- **Sound**: voice chain (highpass/de-ess/compress, -16 LUFS) on every narration; optional music bed
  from assets/music/ (YouTube Audio Library / MacLeod - see its README) sidechain-ducked under the
  voice; final mix two-pass loudnorm to -14 LUFS (verified -14.2 on the test master).
- Kokoro fixes: model singleton (was reloading the ONNX per call), absolute paths, speed knob (1.05).
- ADR-0009 amended (Orpheus rejected-on-license; NeuTTS Air is the signature-voice upgrade path).

## 2026-07-26 - Ideation, search, credibility (TASK-009/010/011/012/013/014)
- **/ideas**: researcher proposes pitched topics (today-in-history + Wikipedia + SearXNG), persistent
  pick-buttons start the pipeline. User-accepted ("significantly better").
- **SearXNG** self-hosted in WSL2 Ubuntu + docker (infra/searxng/), JSON API, WSL keepalive + memory cap.
- **Credibility layer**: research node gathers an evidence pack; scripts are evidence-grounded with a
  word-count auto-retry; a conservative fact-checker audits every claim and flags them on the Gate 1
  card. Caught a real garbled fact on its first test run.
- Fixes: caption wrapping in safe margins; Discord playback (faststart mp4 + mp3 previews); visual
  quality stack (commercial-safe vector LoRA, dpmpp_2m/karras/32, cudnn-off VAE decode for RDNA1).
- Decisions: Gemma 3n declined (Vulkan load risk + weaker structured output; ledger TASK-012);
  Kurzgesagt-named LoRAs avoided (trade-dress risk).

## 2026-07-25 - MVP COMPLETE: first shorts produced end-to-end (TASK-007 done)
- **The pipeline works**: topic -> schema-constrained script -> Gate 1 -> Kokoro narration -> Gate 2 ->
  automatic GPU choreography (stop brain, render SDXL stills via ComfyUI, restart brain) -> whisper
  word-timed captions -> Ken-Burns 1080x1920 assembly with burned captions -> Gate 3 -> delivery with
  YouTube metadata + AI-disclosure reminder. Two shorts produced: one CLI-driven, one fully
  Discord-driven by the user.
- **Durability proven**: a gate opened in one process was resumed by a different process from the
  SQLite checkpoint; gate buttons are DynamicItems (regex custom_ids) that survive bot restarts.
- New: `src/graph/{build,state}.py`, `src/workers/{tts,visuals,captions,assemble}.py`,
  `src/gateway/client.py`, `src/agents/scriptwriter.py`, `src/bot/{gates,pipeline}.py`,
  `scripts/run_pipeline_cli.py` (also the resume-test harness).

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
