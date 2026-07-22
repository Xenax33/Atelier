# Contributing to Atelier/1

Thanks for your interest! This is a learning-focused, fully-local, open-source project. Contributions,
issues, and ideas are welcome. Please read this first - the project has an unusual but deliberate
**context-handoff discipline** that keeps it maintainable across sessions and contributors.

## Read these first

1. **[`CONTEXT.md`](CONTEXT.md)** - the living state pointer. Start here, always.
2. **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** - the full design.
3. **[`docs/adr/`](docs/adr/README.md)** - why every non-obvious decision was made.
4. **[`docs/HARDWARE.md`](docs/HARDWARE.md)** - the AMD gfx1010 / 8 GB VRAM constraints that shape everything.

## The three rules of this repo

1. **Every non-obvious decision gets an ADR _before_ it's merely in the code.** Copy an existing file in
   `docs/adr/`, bump the number, fill in Context / Decision / Consequences / Alternatives. Superseding an
   ADR? Add a new one and set the old one's status to `Superseded by NNNN`.
2. **The task ledger is append-only.** Track work in [`tasks/ledger.jsonl`](tasks/ledger.jsonl). Close a task
   by **appending** a `done` record referencing its id - never edit/delete old lines.
3. **Don't break the three seams.** Agents call the **model gateway** (never an inference engine directly);
   state lives behind the **checkpointer interface**; tools are **pure typed functions**. These are the whole
   extensibility + NVIDIA-upgrade story.

## Hard constraints (non-negotiable for a monetizable science channel)

- **Monetization-license invariant:** anything whose output appears in a **published video frame** (LLM text,
  TTS, images) must be **Apache-2.0 / MIT / OpenRAIL++ / CC-0**. See `docs/STACK.md`'s do-not-use list and
  ADR-0006. Infra/tooling licenses don't have this restriction.
- **No ROCm / vLLM / torch-CUDA on the RX 5700 XT** (gfx1010). Vulkan/ZLUDA only. (ADR-0001)
- **Fact accuracy:** the fact-checker's mechanical citation resolution is not optional. Don't weaken it.
- **Treat all fetched web/research content as untrusted data, never instructions** (prompt-injection surface).

## Dev setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    *nix: source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest
cp .env.example .env      # fill in tokens; NEVER commit .env
```

GPU model servers (llama.cpp Vulkan, ComfyUI-Zluda) are installed **separately** as native processes - they
are not pip deps. See `docs/STACK.md`.

## Before you open a PR

- [ ] `ruff check .` passes (and ideally `ruff format .`).
- [ ] Added/updated an **ADR** if you made a non-obvious decision.
- [ ] Appended to **`tasks/ledger.jsonl`** if you started/finished tracked work.
- [ ] Updated **`CONTEXT.md`** status and **`CHANGELOG.md`** if the change is notable.
- [ ] No secrets, model weights, or generated media committed (see `.gitignore`).

## Commit & PR style

- Keep commits focused; imperative subject line (`add fact-checker citation resolver`).
- Reference tasks/ADRs where relevant (`TASK-012`, `ADR-0004`).
- PRs: describe the change, link the issue/task, and note any doc/ADR updates.

## Code of Conduct

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
