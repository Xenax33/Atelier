# Changelog

Notable changes, newest first. Keep entries short; link tasks (`TASK-###`) and ADRs where relevant.

## 2026-07-22 — Project bootstrap
- Repo scaffolded; context-handoff system initialized (`CONTEXT.md`, `docs/`, `docs/adr/`, `tasks/ledger.jsonl`).
- Full architecture captured in `docs/ARCHITECTURE.md` (from a 12-agent research + design pass).
- Locked initial decisions via ADRs 0001–0010 (Vulkan-not-ROCm, `--cpu-moe` 30B brain, LangGraph+SQLite spine,
  no local AI video, private-draft publish, Apache-only model invariant, Windows-native runtime, flat-vector
  visual style, Kokoro narrator, editorial taste model).
- Phase 0 tasks seeded in `tasks/ledger.jsonl`.
- Open-sourced under **MIT**: added `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `docs/ROADMAP.md`, GitHub issue/PR templates, a `ruff` CI workflow, `pyproject.toml`, `.gitattributes`,
  and `.editorconfig`. README updated with badges + disclaimer. Public repo: `Xenax33/Atelier`.
