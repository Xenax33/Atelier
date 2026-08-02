# Atelier/1

> A single-owner, fully **local**, fully **open-source**, **human-in-the-loop** pipeline that produces
> ~60-second vertical science Shorts (scientific history and interesting science facts), controlled from
> **Discord**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Xenax33/Atelier/actions/workflows/ci.yml/badge.svg)](https://github.com/Xenax33/Atelier/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Status: Phase 0 (WIP)](https://img.shields.io/badge/status-Phase%200%20(WIP)-orange.svg)](docs/ROADMAP.md)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

It researches topics, drafts and fact-checks candidate scripts, and after you approve at each gate it renders
voiceover, flat-vector visuals, and animated diagrams into a finished 9:16 video, then uploads it as a
**private draft** for you to publish manually.

> **New here? Read [`CONTEXT.md`](CONTEXT.md) first**, then [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Why it's built this way

- **Everything local, nothing paid in the core loop.** Runs on one PC (AMD RX 5700 XT, 64 GB RAM, Windows 11).
- **Monetization-clean by construction.** Every model or asset in a published frame is Apache-2.0, MIT, OpenRAIL++, or CC-0.
- **Credibility first.** A mandatory fact-checker mechanically resolves every citation, because one viral wrong "fact" can sink a science channel.
- **A seamed modular monolith.** One process today, but it grows into services without a rewrite via three seams (the model gateway, the checkpointer interface, and pure-function tools). See `CONTEXT.md`.
- **A learning project.** The stack is chosen partly to teach agent orchestration, durable human-in-the-loop workflows, and local inference.

## Stack (headline picks)

| Layer | Pick |
|---|---|
| Agent brain | **Qwen3-4B-Instruct-2507** via **llama.cpp Vulkan** (93 tok/s measured; 30B MoE planned after a RAM upgrade, see ADR-0011) |
| Orchestration | **LangGraph** (MIT core) + `SqliteSaver` |
| Control plane | **discord.py** 2.6+ |
| Research | Wikipedia/Wikidata APIs + self-hosted **SearXNG** (WSL2 docker) |
| TTS | **Kokoro-82M** (CPU) |
| Images | **SDXL** + vector-style LoRA via **ComfyUI-Zluda** |
| Motion | Ken-Burns over stills (Depth-Anything parallax + **Manim** diagrams planned) |
| Captions / assembly | faster-whisper + ffmpeg/MoviePy |
| Memory | sqlite-vec (topic dedup, live), later pgvector |
| Publishing | manual upload by the owner (metadata auto-drafted; API publishing deferred) |

Full stack with pinned versions and licenses: [`docs/STACK.md`](docs/STACK.md).

## Quickstart

```powershell
copy .env.example .env      # fill in the Discord bot token + server/channel ids
./start-day.ps1             # boots brain + SearXNG + bot, health-gated
# then in Discord:  /ideas  (or /new-short with your own topic)
```

Full setup from scratch (models, ComfyUI-Zluda, WSL/SearXNG): `docs/STACK.md`, `docs/SETUP-COMFYUI.md`,
`docs/RUNBOOK.md`.

## Repo map

```
CONTEXT.md      read first: the living state pointer
docs/           ARCHITECTURE (the plan), HARDWARE, STACK, RUNBOOK, adr/ (decisions)
tasks/          ledger.jsonl (append-only: what's done, what's left)
state/runs/     per-video durable artifact trail
src/            bot, graph, agents, gateway, tools, workers, store
prompts/        versioned prompt templates
start-day.ps1   the one-click launcher
```

## Status

**MVP shipped; v1 core complete.** The full loop works end to end: `/ideas` researches and proposes
topics, the pipeline drafts three fact-checked candidate scripts, and after three human approval gates
a finished 9:16 short with metadata lands ready for manual upload. See [`docs/ROADMAP.md`](docs/ROADMAP.md)
and [`tasks/ledger.jsonl`](tasks/ledger.jsonl) for what's done and what's next.

## Contributing

Contributions, issues, and ideas are welcome. This repo follows a deliberate **context-handoff discipline**
(ADRs before non-obvious decisions, an append-only task ledger, and three architectural seams), so please read
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CONTEXT.md`](CONTEXT.md) first. By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md). For security issues, see [`SECURITY.md`](SECURITY.md).

## Disclaimer

This is an independent, educational project. It is **not affiliated with, endorsed by, or sponsored by**
YouTube, Google, Instagram, or Meta. It automates *content production* with a human in the loop; it does not
attempt to game platform algorithms or bypass platform rules. You are responsible for:

- Complying with **YouTube and Instagram policies** on AI-generated and automated content (including required
  AI-disclosure), and with each **model or asset license** (see below).
- The **accuracy** of anything you publish. The built-in fact-checker reduces this risk but does not eliminate it.

The software is provided "as is", without warranty of any kind (see `LICENSE`).

## License

Licensed under the **[MIT License](LICENSE)**.

> **Important:** the MIT license covers **this repository's own code only**. The AI **models, weights, voices,
> and media assets** the pipeline uses carry their **own** licenses, some of which are non-commercial. The
> project pins to commercially-usable models for any published video frame; see
> [`docs/adr/0006-apache-only-model-invariant.md`](docs/adr/0006-apache-only-model-invariant.md) and
> [`docs/STACK.md`](docs/STACK.md). Complying with those licenses is your responsibility.
