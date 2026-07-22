# RUNBOOK — boot, recover, known failures

Operational playbook. Fill in the TODOs as Phase 0 stands each service up.

## Daily boot

```powershell
./start-day.ps1          # boots GPU servers, health-gates, launches app, pings Discord
./start-day.ps1 -SkipComfy   # text-only iteration (no SDXL)
```

Expected green state (target):
- `http://127.0.0.1:8080/v1/models` returns the loaded Qwen model.
- `http://127.0.0.1:8188` (ComfyUI) responds.
- Discord `#control` shows a "stack ready" message.

## Recover from a crash

- **A GPU server died** → nssm should restart it; otherwise re-run `start-day.ps1`. Verify VRAM freed
  (`no other heavy stage resident` — see HARDWARE.md) before restarting SDXL.
- **App died mid-short** → just relaunch. LangGraph `SqliteSaver` checkpoints per `thread_id`; the run
  resumes from its last gate. (Prove this in MVP DoD: kill mid-run, confirm resume.)
- **A Discord gate button is dead after a restart** → Views must be re-registered as **persistent** on
  startup; check `src/bot` registers them. Interactions expire (~15 min) — reply via message edits.

## Known failures & fixes

| Symptom | Cause | Fix |
|---|---|---|
| Torch/ROCm build errors, silent CPU fallback | Someone tried ROCm/vLLM on gfx1010 | Don't. Vulkan/ZLUDA only. (ADR-0001) |
| OOM during image gen | Two heavy GPU stages co-resident | Serialize; unload before SDXL. (HARDWARE.md) |
| ComfyUI-Zluda stopped working after an update | Triton/flash-attn drift | Restore the venv snapshot. (STACK.md) |
| Fact-checker passes a fabricated DOI | Trusted model self-citation | Citations must be **mechanically resolved** (HTTP 200 + Crossref/OpenAlex title match) |
| Discord "file too large" on final review | 10 MB attachment cap vs ~40-60 MB master | Serve via Caddy/cloudflared link + sub-10 MB proxy |
| YouTube upload forced to private / rejected | Unverified project / quota / policy | Private-draft is by design; verify project; check quota |

## Boot-time TODOs (Phase 0)
- [ ] TASK-001: real llama.cpp Vulkan launch command here.
- [ ] TASK-002: real ComfyUI-Zluda launch command + venv snapshot location here.
- [ ] TASK-003: Kokoro smoke test command.
- [ ] TASK-006: Discord "stack ready" webhook wiring.
