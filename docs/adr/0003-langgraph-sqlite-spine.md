# 0003 — LangGraph (MIT core) + SqliteSaver as the durable HITL spine
Status: Accepted
Date: 2026-07-22

## Context
The pipeline is human-in-the-loop with gates that may sit open overnight (PC gets shut down). State must
survive restarts, and gate approvals must resume exactly where they left off. This is also a learning project.

## Decision
Use **LangGraph MIT core** with `interrupt()` / `Command(resume=)` for gates and **`SqliteSaver`** for
checkpointing, one `thread_id` per short. State lives behind LangGraph's **checkpointer interface** so it
swaps to `PostgresSaver` at v1+ with a one-line change. Agents coordinate **in-process through the shared
state object** — no message bus on day one.

## Consequences
- Easy: durable gates map 1:1 to Discord buttons; survives nightly shutdown; high-leverage skill to learn.
- Hard: LangGraph's learning curve; single-process concurrency limits (fine for one owner).
- Revisit when: you want durable-execution-as-a-discipline → Temporal is a clean v2 swap (state already externalized).

## Alternatives rejected
- **In-memory state** — loses everything on shutdown (footgun R11).
- **LangGraph Platform / langgraph-api** — Elastic License 2.0; keep to MIT core only.
- **Temporal now** — heavier than needed for a single-owner MVP; deferred to optional v2.
