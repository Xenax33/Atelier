# 0010 — Two-tier memory: production/episodic store + a learned editorial taste model
Status: Accepted
Date: 2026-07-22
_User requirement (2026-07-22): "the scriptwriter needs all past context AND to learn what I like over time."_

## Context
The user wants agents to (a) retain everything the channel has produced (avoid repeats, stay consistent) and
(b) **learn the user's editorial taste over time**. These are two different concerns and must not be conflated.

## Decision
Build **two distinct memory systems:**

1. **Production / episodic memory** — every topic, candidate script (picked *and* rejected), asset, and final
   video is embedded (bge-m3) into the dedup/vector store (`sqlite-vec` → `pgvector`). Powers dedup,
   fact-consistency, and reusable research.
2. **Editorial taste model** — a living **`prompts/editorial-profile.md`** the Scriptwriter/Editor read on
   **every** run, learned from:
   - *Explicit* signals ("I like ≤2s hooks", "no clickbait") captured via a Discord command.
   - *Implicit* signals: which candidate the user picks at Gate 1, and — highest signal — **the diff between
     the drafted script and the user's approved edit**; plus 👍/👎 reactions.
   Guardrails: a periodic **reflection/consolidation** pass (condense, don't hoard), and a
   `what-do-you-think-my-style-is` command so the user can **inspect and correct** the profile (prevent drift).

## Consequences
- Easy: visible personalization over time; dedup + consistency for free from the same embeddings.
- Hard: needs signal capture plumbing at Gate 1 (diff + choice logging) and a consolidation schedule.
- Revisit when: enough runs exist to correlate taste-profile changes with retention metrics (v2 eval loop).

## Alternatives rejected
- **One RAG store for everything** — conflates "what we made" with "what the user likes"; taste signal gets lost.
- **Fine-tuning a local model on the user's edits** — premature; a read-every-run profile doc is cheaper,
  inspectable, and correctable.
