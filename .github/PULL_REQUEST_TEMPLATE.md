<!-- Thanks for contributing! Keep PRs focused. See CONTRIBUTING.md. -->

## What & why
<!-- What does this change, and why? Link the issue/task, e.g. Closes #12 / TASK-014 / ADR-0007. -->

## Checklist
- [ ] `ruff check .` passes
- [ ] Added/updated an **ADR** in `docs/adr/` if this involved a non-obvious decision
- [ ] Appended to **`tasks/ledger.jsonl`** if this started/finished tracked work
- [ ] Updated **`CONTEXT.md`** / **`CHANGELOG.md`** if the change is notable
- [ ] Did **not** break the three seams (model gateway · checkpointer · pure-fn tools)
- [ ] Respects the monetization-license invariant (ADR-0006) if it touches models/assets
- [ ] No secrets, model weights, or generated media committed

## Notes for reviewers
<!-- Anything tricky, follow-ups, or things you're unsure about. -->
