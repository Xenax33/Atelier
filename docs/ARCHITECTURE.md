> **This is the living source-of-truth architecture.** Generated 2026-07-22 from a 12-agent research+design pass. Keep it current; when a decision changes, add/append an ADR in `docs/adr/` and update the relevant section here.

---

# Local Open-Source Science-Shorts Studio - Definitive Build Plan

*Target box: Ryzen 5 5600, 64 GB DDR4, RX 5700 XT (gfx1010 / RDNA1, 8 GB), Windows 11. Goal: a fully local, fully open-source, human-in-the-loop pipeline that runs a "scientific history / interesting science" Shorts + Reels channel, controlled from Discord, monetization-clean.*

---

## 1. Executive summary

Build a **seamed modular monolith** - call it **Atelier/1**. It is one Python process (discord.py 2.6 + LangGraph MIT core, SQLite-checkpointed) that starts as simply as Candidate 1, enforces the credibility gates of Candidate 3 (mandatory fact-checker + editor), and is deliberately cut along three seams so it grows into the service architecture of Candidate 2 **without a rewrite**. You ship one correct short this week; you refactor toward services only when a stage actually hurts.

The opinionated core decisions:

1. **One process, three seams.** The bot and the orchestrator are the same asyncio process (no IPC, no broker on day one). But agents never import an inference engine (they call an **OpenAI-compatible model gateway**), state lives behind LangGraph's **checkpointer interface** (`SqliteSaver` now, `PostgresSaver` later - a one-line swap), and every tool is a **pure typed function** (wrap as MCP/queue-RPC later). These three seams are the entire difference between "learning-grade extensible" and "big ball of mud."
2. **The `--cpu-moe` MoE brain is the hardware insight that unlocks the rest.** Qwen3-30B-A3B Q4_K_M via **llama.cpp Vulkan** with `--cpu-moe` parks its experts in your 64 GB RAM and uses **~2 GB VRAM**, so the 30B-class brain stays *permanently resident* and never fights SDXL for the 8 GB. This is why you get 30B reasoning + reliable tool-calling on an 8 GB card.
3. **The fact-checker is the product, not a feature.** For a science-history niche, one viral wrong "fact" is a kill-shot, and local models fabricate citations at 11-57%. A mandatory retrieval-grounded fact-checker that *mechanically resolves every citation* (HTTP 200 + Crossref/OpenAlex title match) plus a human approval gate is simultaneously your quality moat and your survival mechanism against YouTube's 2026 inauthentic-content policy.
4. **No local AI video. Ever, on this box.** Motion = SDXL stills + Depth-Anything-V2 2.5D parallax + Ken-Burns + **Manim** diagrams. This is honest for RDNA1 and *better* for the niche (clean animated science diagrams beat hallucinated video).
5. **Publish as a private draft; the human clicks "Publish."** That click sidesteps YouTube's API Compliance Audit *and* is exactly the human oversight the inauthentic-content policy rewards.
6. **Everything in a published frame is Apache-2.0 / MIT / OpenRAIL++ / CC-0.** Monetization safety is a build invariant, not a later audit.

Everything runs **native on Windows 11 via Vulkan/ZLUDA** launched by one PowerShell script. No ROCm, no vLLM, no dual-boot, no paid cloud in the core loop.

---

## 2. Hardware reality check

The RX 5700 XT is **gfx1010 / RDNA1**: no official ROCm in 2026 (dropped after ROCm 5.2, never restored), no fast FP16/WMMA matrix cores, no reliable Docker GPU passthrough on Windows/WSL2, and the old `HSA_OVERRIDE_GFX_VERSION=10.3.0` shim is dead on torch ≥ 2.0. **Do not build anything on ROCm/vLLM/PyTorch-CUDA-expectations for this card.** The only reliable GPU paths are **Vulkan** (llama.cpp, Orpheus) and **ZLUDA** (ComfyUI/SDXL). Your 64 GB RAM is the real asset - it is what makes MoE offload and CPU-side TTS/diagram rendering excellent.

| Workload | Verdict on this box | Path |
|---|---|---|
| **LLM (agent brains)** | **Good.** 30B-class quality is achievable. | `llama.cpp` **Vulkan** server, Qwen3-30B-A3B Q4_K_M `--cpu-moe` (experts in RAM, ~2 GB VRAM, ~30 tok/s). Qwen3-8B dense fully in VRAM (~45-55 tok/s) as a fast lane. **Never ROCm.** |
| **TTS (narration)** | **Trivial - not a bottleneck.** GPU essentially irrelevant. | **Kokoro-82M via `kokoro-onnx` on CPU** (~5-15× realtime; 60 s renders in seconds). Optional GPU emotive path: **Orpheus-3B GGUF via llama.cpp Vulkan** + SNAC decoder. |
| **Image (stills)** | **Feasible but slow.** ~1-5 min / 1024px image. | **ComfyUI-Zluda** (native Windows), **SDXL 1.0** at 768×1344 with `--lowvram` + tiled VAE. Flux.1 **schnell** GGUF only as occasional hero-frame (much slower). |
| **Video (generative t2v/i2v)** | **Not feasible at a daily cadence.** RDNA1 has no matrix accel; every "runs on 8 GB" claim is benchmarked on NVIDIA. | **Skip it.** Fake motion: **Depth-Anything-V2** parallax + **Ken-Burns** + **Manim** diagrams. AnimateDiff/Wan/SVD are overnight experiments at best (and SVD/Flux-dev are non-commercial anyway). |
| **Embeddings / dedup / captions** | **Trivial on CPU.** | `bge-m3` or `bge-small-en-v1.5` on CPU; **whisperX / faster-whisper** on CPU (or GPU when idle). |
| **Orchestration / Discord / DBs** | **Free.** ~0 % GPU, a couple GB RAM. | Pure asyncio + SQLite/Postgres. Runs comfortably in the background; could even run on the i3 laptop. |

**OS / runtime recommendation:** **stay Windows-native + Vulkan/ZLUDA.** Linux buys maybe 10-20% and cleaner Docker, but **WSL2 GPU passthrough for AMD is weak** - do not route inference through WSL2. The GPU model servers must be **native Windows processes** regardless of OS choice. Dual-boot is optional and low-value here; the single change that would actually remove these constraints is a **GPU upgrade to a 16 GB card with matrix cores** (see Open Decisions).

**The one VRAM rule that governs the whole design:** 8 GB holds **one heavy GPU stage at a time**. Because the `--cpu-moe` brain is ~2 GB VRAM, *text reasoning can overlap with anything*, but the heavy GPU stages - **SDXL, GPU-whisper, Orpheus** - must be **serialized** among themselves. The workflow enforces stage ordering; never hope two heavy models co-reside.

---

## 3. Recommended stack

Every generative/model pick below is **monetization-safe by construction**. Runtime/infra licenses (MIT/BSD/Apache/AGPL) never touch the published frame - they are noted only where a strict "fully open-source" reading matters.

| Layer | Pick (version) | Why | License / monetization note |
|---|---|---|---|
| **LLM runtime** | **llama.cpp Vulkan server** (prebuilt vulkan release) | Only reliable gfx1010 path; GBNF/JSON-schema constrained decoding; identical Win/Linux | MIT (engine). Runtime license is monetization-irrelevant. |
| **Primary brain** | **Qwen3-30B-A3B Q4_K_M** `--cpu-moe` | 30B reasoning + reliable tool-calling at ~2 GB VRAM / ~30 tok/s on this exact box | **Apache-2.0 -> outputs fully safe to monetize.** |
| **Fast-lane brain** | **Qwen3-8B Q4_K_M** (fully in VRAM) | Cheap routing/tagging/short rewrites (~45-55 tok/s) when GPU idle | Apache-2.0. Safe. |
| **Structured output** | **GBNF / JSON-schema constrained decoding** | Converts a local model into a reliable data-emitter; kills malformed tool-JSON | Technique; no license/monetization impact. |
| **Model gateway** | **LiteLLM proxy** *or* a ~150-line FastAPI facade (OpenAI-compatible) | The pluggable-backend seam; single request queue (8 GB = one instance) | MIT. Infra only. |
| **TTS (default)** | **Kokoro-82M** via `kokoro-onnx` (CPU) | Clean explainer VO in seconds, zero GPU, **preset voices = zero likeness risk** | **Apache-2.0 -> safe.** |
| **TTS (emotive, optional)** | **Orpheus-3B GGUF** via llama.cpp Vulkan + SNAC | The one clean GPU-TTS route on RDNA1; inline `<laugh>/<sigh>` tags | **Apache-2.0 -> safe.** |
| **TTS (signature voice, optional)** | **Chatterbox-Turbo** (CPU) | If you want a branded narrator - **clone ONLY your own consented voice** | MIT engine. *MIT does not cover voice identity - own-voice-only.* |
| **Image model** | **SDXL 1.0 base** (+ style LoRAs) in ComfyUI-Zluda | Fits 8 GB, huge ControlNet/LoRA ecosystem for consistent flat-vector look | **CreativeML Open RAIL++-M, no revenue cap -> safe.** |
| **Hero-frame (optional)** | **Flux.1 schnell** GGUF Q4/Q5 | Better text/coherence for occasional hero frames | **Apache-2.0 -> safe.** *Avoid Flux.1 **dev** (non-commercial).* |
| **Depth / parallax** | **Depth-Anything-V2** | Depth maps -> 2.5D displacement for convincing motion over stills | Apache-2.0. Safe. |
| **Motion graphics** | **Manim Community Edition** (+ matplotlib; Motion Canvas optional) | The niche's real differentiator: animated diagrams/timelines/math, CPU-rendered | MIT / BSD / MIT. Safe. |
| **Captioning** | **whisperX** (or faster-whisper) | Word-level timestamps for burned-in animated captions | BSD-2 / MIT. Safe. |
| **Assembly / encode** | **MoviePy + ffmpeg**, 1080×1920 H.264 | Zero license clause; Ken-Burns, compositing, burn-in captions | MIT / LGPL. *Chosen over Remotion to dodge its 4+-employee Company License.* |
| **Orchestration** | **LangGraph MIT core** + `SqliteSaver`, `interrupt()`/`Command(resume=)` | Durable HITL maps 1:1 to Discord gates; survives nightly shutdown; top agent skill to learn | **MIT.** *Do NOT use langgraph-api / LangGraph Platform (Elastic License 2.0).* |
| **Discord** | **discord.py 2.6.x** (Components V2 / LayoutView), single bot + webhook personas | Largest example corpus; Container cards + Modals = candidate-script approval UI | MIT. Safe. |
| **Embeddings** | **bge-m3** (or bge-small-en-v1.5) on CPU | Consistent model for both dedup and retrieval | MIT. Safe. |
| **Vector / dedup store** | **sqlite-vec** in the checkpoint DB (MVP) -> **Postgres + pgvector** (v1+) | Start as one file; graduate to SQL-joinable metrics store | MIT / PostgreSQL license. Safe. |
| **State / storage** | **SQLite** (MVP) -> **Postgres** (v1+); local FS for assets; per-run dirs | The persistence layer is a file until scale demands a server | Public domain / PostgreSQL license. |
| **Job execution** | `loop.run_in_executor` / subprocess (MVP) -> **arq + Valkey** (v2) | Keep the gateway non-blocking; extract a worker only when the bot must stay responsive mid-render | MIT / BSD-3. *Valkey over Redis to dodge the Redis 8 AGPL question.* |
| **Observability** | **OpenLLMetry** (instrument) + **Phoenix** (view) -> **Langfuse** (evals, v2) | Instrument once via OTel; swap viewers without re-instrumenting | Apache-2.0 / **Phoenix ELv2 (source-available, not OSI)** / Langfuse MIT. |
| **Preview delivery** | **Caddy/nginx** static + **Cloudflare Tunnel** | Works around Discord's **10 MB** upload cap for the ~40-60 MB master | Apache-2.0 / BSD. Safe. |
| **Publishing** | **google-api-python-client**, `youtube.videos.insert` `privacyStatus=private` + AI-disclosure flag | Private-draft + human publish; sidesteps API Compliance Audit | Apache-2.0. Safe. IG deferred to manual. |
| **Secrets** | **SOPS + age** (or git-ignored `.env`, strict perms) | Serverless; Discord token and YouTube OAuth in **separate scopes** | MPL-2.0 / Apache. Safe. |
| **Launcher / supervision** | **PowerShell `start-day.ps1`** + **nssm** + optional Task Scheduler (at-logon) | One action boots + health-gates both native GPU servers, then the app | OS-bundled / free. |

**Explicit "downloadable-but-DO-NOT-USE" list** (monetization traps): Flux.1 **dev**, **Stable Video Diffusion**, **F5-TTS** (CC-BY-NC), **Coqui/XTTS v2** (CPML non-commercial), **Fish OpenAudio S1/S2** (research license), **SD3.5** (< $1M cap), **LTX-Video** (< $10M cap), and **Piper voice checkpoints** with NC/research licenses (the engine is fine; audit each voice). On the infra side, avoid **LangGraph Platform** (Elastic) and **n8n** (fair-code, not OSI) if "fully open-source" is strict.

---

## 4. System architecture

### Components (MVP topology - all native Windows, one process + two GPU servers)

```
                          ┌─────────────────────────────────────────────┐
                          │           start-day.ps1 (launcher)           │
                          │  boots + health-gates everything, pings you  │
                          └───────────────┬──────────────┬──────────────┘
                                          │              │
              ┌───────────────────────────▼───┐   ┌──────▼───────────────────────┐
              │  llama.cpp Vulkan server       │   │  ComfyUI-Zluda (SDXL)        │  ← NATIVE (nssm-supervised)
              │  Qwen3-30B-A3B --cpu-moe       │   │  native Windows, port :8188  │     GPU servers
              │  OpenAI-compatible :8080       │   └──────────────────────────────┘
              └───────────────▲────────────────┘
                              │ (model gateway seam)
   ┌──────────────────────────┴───────────────────────────────────────────────────┐
   │  Atelier/1  - ONE asyncio process                                              │
   │                                                                                │
   │   discord.py 2.6 gateway  ◄──buttons/modals──►  LangGraph StateGraph           │
   │   (Components V2 cards)                          (SqliteSaver, 1 thread/short)  │
   │                                                                                │
   │   Agents (LLM):  Researcher, Fact-Checker, Scriptwriter, Editor, VisDir    │
   │   Workers (det.): TTS(Kokoro), Captions(whisperX), Manim, Assemble(ffmpeg)  │
   │                   , Publisher(youtube api)                                     │
   │                                                                                │
   │   Stores:  SQLite (checkpoints + sqlite-vec dedup), /state/runs/<id>/ (assets)│
   │   Cross-cut: OpenLLMetry -> Phoenix, SOPS secrets, Caddy+cloudflared preview  │
   └────────────────────────────────────────────────────────────────────────────────┘
```

At **v2**, the CPU plane (bot+graph, Postgres, Phoenix, Caddy) moves into **Docker Compose on WSL2**, the two GPU servers stay native and are reached via `host.docker.internal`, and the render worker is extracted behind **arq+Valkey**. The seams above make that a config change, not a rewrite.

### End-to-end dataflow (Discord trigger -> published draft)

```mermaid
flowchart TD
    A["/new-short slash command"] --> B[Researcher: ideate topic]
    B --> C{Dedup gate<br/>pgvector/sqlite-vec + MinHash}
    C -- near-duplicate --> B
    C -- novel --> D[Researcher: multi-source retrieval<br/>Wikidata,OpenAlex,S2,arXiv,Crossref]
    D --> E[Scriptwriter: 3-5 candidate 60s specs]
    E --> F[Fact-Checker: claim->evidence-><br/>HARD citation resolution HTTP200+title-match]
    F --> G[Editor: retention + house-style critique]
    G ==>|**GATE 1 interrupt()**| H["Discord: candidate cards<br/>Approve / Edit(modal) / Regenerate / Reject"]
    H -->|Command resume| I["TTS: Kokoro/Orpheus -> WAV"]
    I ==>|**GATE 2 interrupt()**| J["Discord: audio preview (<10MB)"]
    J -->|Command resume| K[Visuals: SDXL stills -> Depth parallax<br/>+ Manim diagrams]
    K --> L[Assemble: ffmpeg+MoviePy 9:16 master<br/>+ whisperX burned captions]
    L --> M["Caddy/cloudflared review link<br/>+ sub-10MB proxy in Discord"]
    M ==>|**GATE 3 interrupt()**| N[Discord: Approve / Reject final]
    N -->|Command resume| O["Publisher: youtube.videos.insert<br/>privacyStatus=PRIVATE + AI-disclosure flag"]
    O --> P[You flip Public in Studio]
    P --> Q[Write embedding+metrics to dedup store]
```

**Three hard human gates**, each a durable `interrupt()` that survives an overnight shutdown:
- **Gate 1 - Script pick/edit** (the quality + originality gate; low-confidence claims surfaced here for a ruling).
- **Gate 2 - Audio approval** (cheap, fast, catches TTS mispronunciations before the expensive visual stage).
- **Gate 3 - Final review** (served as a link, not a Discord attachment, because a 40-60 MB master exceeds the 10 MB cap).

The **publish click in YouTube Studio** is the fourth, deliberate, human action - not automated.

---

## 5. The agent roster

Distinguish **agents** (LLM-reasoning, behind the model gateway) from **workers** (deterministic pipeline stages). All coordinate **in-process through the shared LangGraph state object** - no message bus, no A2A envelopes, no cross-process serialization on day one.

| Name | Type | Job | Tools / backends | Output into shared state |
|---|---|---|---|---|
| **Researcher** | Agent | Topic ideation + multi-source evidence gathering | Wikidata SPARQL (CC-0), OpenAlex, Semantic Scholar, arXiv (metadata only), Crossref; Wikipedia REST as *leads only*; light throttled yt-dlp for competitor signal | `topic`, `evidence[]`, `sources[]` |
| **Dedup gate** | Worker | Reject near-duplicates of the back-catalog | bge-m3 embeddings + cosine threshold **and** MinHash/Jaccard | `is_novel`, `nearest_prior` |
| **Fact-Checker** | Agent + mechanical | **Mandatory.** Segment -> per-claim retrieval -> entailment -> **resolve every citation (HTTP 200 + Crossref/OpenAlex title-match)** -> confidence | 30B brain (entailment) + Crossref/OpenAlex resolver | `claims[]{claim_id, evidence, citation, confidence}` |
| **Scriptwriter** | Agent | Emit 3-5 machine-readable 60 s vertical specs, grounded **only** in verified claims | 30B brain, GBNF-constrained JSON | `candidates[]` (see spec below) |
| **Editor / Showrunner** | Agent | Second-pass critic: ≤12-word hook in ≤2 s, pattern-interrupt every 5-8 s, surprising fact early, one soft CTA, **varied hook type across videos** | 30B brain | `critiques[]`, ranked candidates |
| **Visual Director** | Agent | Turn each beat into a 9:16 SDXL prompt or a Manim diagram spec (generic style, never brand names) | 30B/8B brain | per-beat `visual_cue[]` |
| **TTS worker** | Worker | Render approved script to narration | Kokoro (CPU) / Orpheus (Vulkan) | `audio.wav` |
| **Captions worker** | Worker | Word-level timing for burn-in | whisperX (CPU/GPU) | `captions.json` |
| **Manim / Stills worker** | Worker | Render diagrams (CPU) + SDXL stills (GPU) + Depth parallax | Manim CE, ComfyUI-Zluda, Depth-Anything-V2 | `assets/` |
| **Assembler** | Worker | Composite 9:16 master + proxy | ffmpeg + MoviePy | `master.mp4`, `proxy.mp4` |
| **Publisher-Assistant** | Agent + worker | Draft title/description/tags; upload as **private draft** with AI-disclosure flag | 8B brain + google-api-python-client | `youtube_video_id` (private) |

**The 60-second spec** (the contract between Scriptwriter and every downstream worker), emitted as GBNF-constrained JSON:

```json
{
  "video_id": "2026-07-22-oersted-compass",
  "hook":    { "t": [0, 2],  "text": "A twitching compass needle rewrote physics.", "type": "curiosity-gap" },
  "context": { "t": [2, 8],  "text": "Copenhagen, 1820. A lecture demo goes wrong." },
  "beats": [
    { "t": [8, 20],  "claim_id": "c1", "citation": "10.xxxx/...", "narration": "...", "visual_cue": "manim:field-lines", "caption": "..." }
  ],
  "payoff":  { "t": [45, 55], "text": "...keeps the promise the hook made." },
  "cta":     { "t": [55, 60], "text": "Follow for the story physics textbooks skip." }
}
```

### Open Floor Protocol / A2A / MCP verdict - **defer all three from the core loop**

All six agents live in one repo and talk through the LangGraph state object, so **OFP and A2A add a serialization + discovery + envelope tax with zero payoff** - they are the wrong layer for a single-owner in-process pipeline. Reach for them *only* if you later expose an agent as a networked service to third parties. **MCP** is the one worth a second look, but only in **v2**, and only for **tools** (wrapping Wikidata/Crossref/YouTube clients as reusable MCP servers is a reasonable learning investment and gives clean reuse). Keep tools as plain typed functions until then. "OpenCode"/"OpenClo" is **OpenCode** (MIT terminal coding agent) / **Cline** (VS Code extension) - those are **dev tools to build this pipeline**, not runtime pipeline agents.

---

## 6. Phased roadmap

Each phase has a hard **Definition of Done (DoD)** - a testable gate, not a vibe.

### Phase 0 - Environment + one-click skeleton
**Deliverables:**
- llama.cpp Vulkan server running **Qwen3-30B-A3B Q4_K_M `--cpu-moe`**, verified via a curl to the OpenAI-compatible endpoint; measure real tok/s and VRAM.
- **ComfyUI-Zluda** generating one SDXL 768×1344 image (pin **Triton 3.0.0** + gfx1010-patched flash-attn wheel; **snapshot the venv immediately**).
- **Kokoro** rendering a 60 s WAV on CPU.
- Hello-world **discord.py 2.6** bot posting a Components V2 card with a working button.
- **`start-day.ps1`** boots both GPU servers, health-gates their endpoints, launches the app, posts "stack ready" to Discord; **nssm** restarts a crashed GPU server.
- Repo scaffold + context-handoff system (Section 7) initialized.

**DoD:** From a cold boot, one command brings the whole stack up green, and you can independently produce (a) an LLM completion, (b) an SDXL image, (c) a Kokoro clip - each confirmed in Discord. The ZLUDA venv is snapshotted and documented in `RUNBOOK.md`.

### MVP - end-to-end single short, heavy human-in-loop
**Deliverables:**
- LangGraph StateGraph with the full **linear** flow and `SqliteSaver` (one `thread_id` per short).
- Minimal intelligence: you **hand-feed a topic and a script**; agents are thin. All three gates are live `interrupt()`s.
- Real render: Kokoro VO -> SDXL stills + Ken-Burns + **one Manim diagram** -> whisperX burned captions -> ffmpeg 9:16 master.
- Caddy/cloudflared review link + sub-10 MB proxy in Discord.
- Publisher uploads as **private draft** with the **altered/synthetic disclosure flag hard-coded on**.

**DoD:** One hand-fed topic becomes a published **private-draft** YouTube short with voiceover, burned captions, at least one Manim diagram over stills, reviewed via link, resumable across a PC restart (kill the process mid-run and prove it resumes from the checkpoint).

### v1 - the credibility + memory + intelligence layer
**Deliverables:**
- **Researcher** with real multi-source retrieval; **dedup gate** (sqlite-vec + MinHash) blocking repeats.
- **Fact-Checker** as a non-skippable node with **mechanical citation resolution** and a confidence threshold that routes low-confidence claims to Discord.
- **Scriptwriter** emitting 3-5 GBNF-constrained candidate specs; **Editor** critique + ranking; **Visual Director** prompts.
- **Model gateway** in front of the LLM (agents stop importing the client directly).
- **OpenLLMetry -> Phoenix** tracing live; per-run state dirs fully populated.

**DoD:** From a one-line seed, the pipeline auto-drafts 3 fact-checked candidates (every citation mechanically resolved or flagged), dedups against the back-catalog, you pick/edit at Gate 1, and it renders + drafts unattended through the remaining gates. Phoenix shows per-agent latency + token spend for the run.

### v2 - hardening, extension, second platform
**Deliverables (pick per Open Decisions):**
- **Containerize the CPU plane** (Docker Compose on WSL2); **SqliteSaver -> PostgresSaver + pgvector**; cap WSL2 RAM in `.wslconfig`.
- **Extract the render worker** behind **arq + Valkey** so the bot stays responsive during long renders and the next research runs while the current short renders.
- **Instagram Reels** automation *after* Meta App Review (Business/Creator + linked Page), or keep manual.
- **Langfuse** for prompt versioning + eval scoring to iterate on script quality; **hook-type performance** fed back into dedup ("what actually performed").
- Optional: **MCP-wrap** the tools; **signature voice** (Orpheus emotive or your-own-voice Chatterbox); **Temporal** migration *if* you specifically want to learn durable-execution-as-a-discipline (the graph state is already externalized, so it's a clean swap).

**DoD:** Reproducible `docker compose up` control plane + native GPU servers; a second short renders while the first is still in review; prompt/eval iteration loop closes on measured retention; (optional) IG publishing or Temporal spine demonstrably working.

---

## 7. Context-handoff system (first-class requirement)

**Goal:** any future session - you in three weeks, a fresh AI coding agent, or a collaborator - can `cat CONTEXT.md` and within minutes know *what this is, how to run it, what's done, what's left, and why every non-obvious decision was made*. Git is the spine; three artifacts are load-bearing: **CONTEXT.md** (the pointer), **ADRs** (the why), and the **task ledger** (the what's-left). Per-run state dirs are the durable audit trail alongside the SQLite checkpoint.

### Repo layout

```
atelier/
├─ CONTEXT.md               # READ ME FIRST - living state pointer (see template)
├─ README.md                # human-facing project overview + quickstart
├─ CHANGELOG.md             # notable changes, newest first
├─ start-day.ps1            # the one-click launcher
├─ .env.example             # every secret key, with dummy values + scope notes
├─ .wslconfig.example       # v2: WSL2 RAM cap
│
├─ docs/
│  ├─ ARCHITECTURE.md        # this plan, kept current (the source of truth)
│  ├─ STACK.md               # pinned versions + why each; the ZLUDA venv snapshot recipe
│  ├─ RUNBOOK.md             # boot, recover-from-crash, known failures + fixes
│  ├─ HARDWARE.md            # the gfx1010 truths, VRAM budget, serialization rules
│  └─ adr/                   # Architecture Decision Records (numbered, append-only)
│     ├─ 0001-vulkan-not-rocm.md
│     ├─ 0002-cpu-moe-30b-brain.md
│     ├─ 0003-langgraph-sqlite-spine.md
│     ├─ 0004-no-local-ai-video.md
│     ├─ 0005-private-draft-publish.md
│     └─ 0006-apache-only-model-invariant.md
│
├─ tasks/
│  └─ ledger.jsonl           # append-only task ledger (see schema)
│
├─ state/
│  └─ runs/<video_id>/       # per-run durable artifact trail
│     ├─ status.json         # current stage, gate state, timestamps
│     ├─ topic.json          # chosen topic + dedup result
│     ├─ evidence.json       # retrieved sources
│     ├─ claims.json         # claims + citations + confidence + resolution result
│     ├─ spec.json           # the chosen/edited 60s script spec
│     ├─ assets/             # stills, depth maps, manim clips, audio.wav, captions.json
│     ├─ render/             # master.mp4, proxy.mp4
│     └─ decisions.log       # every human gate decision, who/when/what-edited
│
├─ atelier.db                # SQLite: LangGraph checkpoints + sqlite-vec dedup (v1)
│
├─ src/
│  ├─ bot/                   # discord.py gateway, Components V2 cards, gate bridge
│  ├─ graph/                 # LangGraph StateGraph, nodes, state schema
│  ├─ agents/               # one module per agent (researcher, factcheck, ...)
│  ├─ gateway/               # OpenAI-compatible model gateway (the swap seam)
│  ├─ tools/                 # pure typed functions (wikidata, crossref, youtube, ...)
│  ├─ workers/               # tts, captions, manim, assemble, publish
│  └─ store/                 # checkpointer + dedup interface (SqliteSaver->Postgres)
│
└─ prompts/                  # versioned prompt templates (prompt_v3.md ...)
```

### `CONTEXT.md` template (the single most important file)

```markdown
# CONTEXT - Atelier/1  (last updated: 2026-07-22 by <session>)

## What this is
Local, open-source, Discord-controlled science-Shorts pipeline. One process
(discord.py + LangGraph), two native GPU servers (llama.cpp Vulkan, ComfyUI-Zluda).

## Current phase / status
Phase: v1 (credibility layer).  Last green run: 2026-07-21 (video_id=...).
Health: llama-server OK, ComfyUI OK, Fact-Checker citation-resolver: FLAKY (see TASK-042).

## How to run
`./start-day.ps1` -> wait for "stack ready" in #control -> `/new-short`.
Full boot + recovery: docs/RUNBOOK.md.  Hardware truths: docs/HARDWARE.md.

## Architecture & decisions
Living plan: docs/ARCHITECTURE.md.  Why-decisions: docs/adr/ (start at 0001).
The three seams (do not break): model gateway, checkpointer interface, pure-fn tools.

## What's done / in-progress / next
Authoritative: tasks/ledger.jsonl.  Top 3 open: TASK-042, TASK-045, TASK-050.

## Known traps (bit us before)
- ZLUDA venv breaks on Triton bump -> restore snapshot (STACK.md §venv).
- Never co-resident SDXL + GPU-whisper (OOM). Serialize. (HARDWARE.md §vram)
- Wikipedia prose is CC-BY-SA -> extract facts, rewrite, never quote.
```

### ADR template (`docs/adr/NNNN-slug.md`)

```markdown
# NNNN - <decision title>
Status: Accepted | Superseded by NNNN | Deprecated
Date: 2026-07-22
## Context
<the forces: hardware limit, license, policy, time budget>
## Decision
<what we chose>
## Consequences
<what this makes easy, what it makes hard, what to revisit and when>
## Alternatives rejected
<e.g. ROCm/vLLM - rejected because gfx1010 unsupported; ...>
```

### Task ledger schema (`tasks/ledger.jsonl`, append-only - one JSON object per line)

```json
{"id":"TASK-042","title":"Crossref resolver 429s under burst","status":"in_progress","phase":"v1","priority":"high","owner":"session-2026-07-22","created":"2026-07-20","blocks":["v1-DoD"],"notes":"add backoff+cache; S2 needs free API key","links":["src/tools/crossref.py"]}
{"id":"TASK-045","title":"Editor hook-type variety enforcement","status":"todo","phase":"v1","priority":"med","notes":"log hook_type to dedup store; reject 3rd same-type in a row"}
```

**Status vocabulary:** `todo | in_progress | blocked | done | wontfix`. **Rules of the system:** (1) every non-obvious choice gets an ADR *before* it's coded; (2) the ledger is append-only - you close a task by appending a `done` record referencing the id, never by deleting; (3) `CONTEXT.md` is updated at the end of every working session (a `stop` hook or a checklist item); (4) each run's `decisions.log` + `status.json` make any short's full history reconstructable independent of the SQLite checkpoint. This scheme is deliberately plain-text + git so it survives tool changes and is equally readable by a human or an agent.

---

## 8. Risk register

| # | Risk | Sev | Mitigation |
|---|---|---|---|
| R1 | **ROCm trap** - building on ROCm/vLLM/torch-CUDA for gfx1010 silently falls back to CPU or won't build | High | Vulkan-only for LLM/Orpheus; ZLUDA for SDXL; ADR-0001 makes it a documented invariant. |
| R2 | **8 GB co-residency OOM** - two heavy GPU stages resident at once | High | `--cpu-moe` brain (~2 GB) never fights SDXL; **serialize** SDXL/GPU-whisper/Orpheus; workflow owns ordering + explicit unload; health-gate before every GPU step. |
| R3 | **ComfyUI-Zluda fragility** - Triton 3.0.0 pin + gfx1010 flash-attn wheel breaks on version bumps | High | **Snapshot the working venv** (STACK.md recipe); if setup exceeds one day, ship MVP with Manim + gradient title cards + Pexels b-roll and add SDXL later. |
| R4 | **Citation hallucination (11-57%)** - model fabricates DOIs/dates/attributions | High | **Mandatory** Fact-Checker: independent retrieval + entailment + **mechanical citation resolution** (HTTP 200 + Crossref/OpenAlex title-match); drop unentailed claims; human rules sub-threshold. Never trust self-citation. |
| R5 | **YouTube inauthentic/mass-produced policy (2026, 3-strike)** - targets templated TTS-over-visuals | High | Human curation gates + per-video dedup + varied hook types + genuine originality; **keep the human publish click** - do not chase zero-touch. |
| R6 | **AI-disclosure miss** - synthetic voice without the "altered/synthetic" label risks a strike | Med | **Hard-code the disclosure flag on** at upload; it carries no monetization/reach penalty. |
| R7 | **Model/asset license traps** - Flux-dev, SVD, XTTS, F5-TTS, Fish, SD3.5/LTX caps, NC Piper voices | High | Pin to **Apache-2.0 / MIT / OpenRAIL++ / CC-0** in every published frame; per-voice allowlist for Piper; ADR-0006 makes it an invariant. |
| R8 | **Voice-cloning right-of-publicity** - cloning a third party is an impersonation risk regardless of MIT weights | Med | Preset Kokoro voices, or clone **only your own consented voice**. |
| R9 | **Wikipedia CC-BY-SA leakage** - close paraphrase creates a derivative/attribution obligation | Med | Wikipedia = *leads only*; **extract facts, rewrite**; Wikidata (CC-0) is the copy-safe spine. |
| R10 | **Discord 10 MB cap + event-loop block + ~15 min token expiry** | Med | Review via **Caddy/cloudflared link** + sub-10 MB proxy; every heavy step off the loop via `run_in_executor`/subprocess; **defer** interactions and reply via message edits; register **persistent Views** for restart survival. |
| R11 | **Durability footgun** - in-memory checkpointer loses all state on the nightly shutdown | Med | **`SqliteSaver` from day one**, keyed per-short by `thread_id`. |
| R12 | **API quota / verification gates** - YouTube force-locks unverified-project uploads to private; Meta App Review 2-6 weeks | Med | Design *for* private-draft (it's a feature); `videos.insert` quota is trivial at your volume; defer IG automation until it's worth the review. |
| R13 | **Prompt injection via research stage** - web/Wikipedia content carries hidden instructions | Med | Treat all fetched content as **untrusted data, never instructions**; keep the human gate strictly between draft and publish. |
| R14 | **Credential blast radius** - bot triggers GPU jobs and (later) publishes to monetized accounts | Med | Discord token and YouTube/IG OAuth in **separate SOPS scopes**; minimal Gateway Intents (no Message Content); every irreversible action behind a logged human button. |
| R15 | **WSL2 RAM ballooning (v2)** - starves the native GPU processes | Low | Cap WSL2 RAM in `.wslconfig`; keep GPU servers native. |

---

## 9. Open decisions for the user

Each is a genuine fork that needs your call. My recommendation is bolded.

1. **OS / runtime.** Windows-native Vulkan/ZLUDA **(recommended)** vs Linux dual-boot vs WSL2. -> *Stay Windows-native.* Linux buys ~10-20% + cleaner Docker; WSL2 AMD passthrough is too weak to trust. Revisit only if you upgrade the GPU.
2. **Autonomy level.** Private-draft + human "Publish" click **(recommended)** vs full auto-publish. -> *Private-draft.* It sidesteps the API Compliance Audit and is the exact human oversight the 2026 policy rewards. One click/video is a compliance feature.
3. **Visual style.** Flat-vector/illustrative (Kurzgesagt/TED-Ed feel) **(recommended)** vs semi-photoreal. -> *Flat-vector.* Easier to keep license-clean and consistent via SDXL LoRAs, and it dodges YouTube's realistic-person disclosure risk entirely. (Never name those brands in prompts.)
4. **Narrator voice.** Neutral preset **Kokoro (recommended default)** vs emotive **Orpheus** vs your-own-voice **Chatterbox** clone. -> *Start Kokoro* (zero likeness risk, zero GPU). Add Orpheus for punchier shorts, or clone **your own** voice if you want a branded identity.
5. **Brain size.** Qwen3-30B-A3B `--cpu-moe` **(recommended)** vs faster dense Qwen3-8B. -> *30B-A3B.* The `--cpu-moe` trick gives 30B reasoning at ~2 GB VRAM; keep the 8B as a fast lane for routing/tagging.
6. **Durability engine.** LangGraph + `SqliteSaver` now **(recommended)**, Temporal as an optional v2 learning module vs go Temporal now. -> *LangGraph now.* It maps 1:1 to your gates and is the higher-leverage agent skill; Temporal is a clean v2 swap **only if** you specifically want to learn durable-execution-as-a-discipline.
7. **Fact-check strictness.** Human-review **only sub-threshold** claims **(recommended)** vs every claim. -> *Sub-threshold.* Full review stalls throughput; the mechanical resolver + threshold catches the dangerous cases. Tighten the threshold for "settled history" vs "frontier science" as you calibrate.
8. **Instagram.** Manual/reminder posting now **(recommended)** vs Meta App Review + Graph API now. -> *Manual first.* Automate YouTube; add IG automation in v2 once volume justifies the 2-6 week review.
9. **GPU upgrade budget.** Keep the 5700 XT **(fine for v1)** vs buy a used 16 GB matrix-core card. -> *This is the single highest-leverage change in the whole project.* A 16 GB card moves local AI video from "impractical" to "feasible," unlocks vLLM/ROCm, and removes nearly every constraint in Sections 2 and 8. Decide before you over-invest in RDNA1 workarounds - but the plan above ships fully on the 5700 XT today if you don't.

---

*This plan is buildable as written on the stated hardware, uses no paid cloud in the core loop, and keeps every published frame monetization-clean. Start at Phase 0, initialize the context-handoff system first, and let the three seams - model gateway, checkpointer interface, pure-function tools - carry you from a one-process monolith to a service studio without a rewrite.*