# RUNBOOK - boot, recover, known failures

Operational playbook. Fill in the TODOs as Phase 0 stands each service up.

## Daily boot

```powershell
./start-day.ps1              # brain + SearXNG + bot (ComfyUI starts per-render automatically)
./start-day.ps1 -WithComfy   # also pre-boot ComfyUI (VRAM rule: brain and SDXL cannot co-reside)
./stop-day.ps1               # full shutdown: frees ~5-6GB VRAM + several GB RAM (closing windows does NOT)
```

Expected green state:
- `http://127.0.0.1:8080/health` returns 200 (llama gateway, Qwen3-4B).
- `http://127.0.0.1:8888/healthz` returns 200 (SearXNG in WSL).
- Discord `#control` shows the boot card; `/status` reports the stack.
- ComfyUI (`:8188`) is only up during renders or with `-WithComfy` - by design (VRAM rule).

## The watchdog (auto-start / self-heal)

`AtelierWatchdog` (Task Scheduler) fires every 5 minutes and runs
`scripts\watchdog-quiet.vbs` -> `start-day.ps1 -IfOn`. The `-IfOn` guard means it only acts
while `state\.studio-on` exists AND its recorded boot id matches the current boot
(start-day stamps it; stop-day clears it). Consequences:

- **The studio NEVER turns itself on after a reboot or power cut** (owner demand
  2026-08-06: it used to, and it was unwanted). After any restart the marker is stale;
  the watchdog deletes it and does nothing. `./start-day.ps1` is the only way to start
  the studio - one manual command.
- WITHIN a session you started yourself, a crashed llama/SearXNG/bot self-heals within
  5 minutes. That is all the watchdog does.
- It does NOT auto-resume an interrupted pipeline run - use Discord `/resume run_id:<id>`.
- Before GAMING: run `stop-day.ps1`. It disarms the marker and frees the ~5-6 GB VRAM the
  brain holds; otherwise the watchdog will fight you for the GPU.
- The task action MUST stay `wscript.exe "...\scripts\watchdog-quiet.vbs"` - invoking
  powershell.exe directly (even with `-WindowStyle Hidden`) flashes a console window at every
  firing, in the middle of whatever the user is doing (found 2026-08-04 after two days of
  mystery cmd popups during games). wscript has no console at all. Re-register with:

```powershell
$a = New-ScheduledTaskAction -Execute "wscript.exe" -Argument '"F:\Side Projects\atelier\scripts\watchdog-quiet.vbs"'
Set-ScheduledTask -TaskName "AtelierWatchdog" -Action $a
```

## Recover from a crash

- **A GPU server died** -> nssm should restart it; otherwise re-run `start-day.ps1`. Verify VRAM freed
  (`no other heavy stage resident` - see HARDWARE.md) before restarting SDXL.
- **App died mid-short** -> just relaunch. LangGraph `SqliteSaver` checkpoints per `thread_id`; the run
  resumes from its last gate. (Prove this in MVP DoD: kill mid-run, confirm resume.)
- **A Discord gate button is dead after a restart** -> Views must be re-registered as **persistent** on
  startup; check `src/bot` registers them. Interactions expire (~15 min) - reply via message edits.

## Kernel-cache snapshots (55-minute-recompile insurance)

gfx1010 kernel compiles are exceptionally slow: a wiped MIOpen/ZLUDA cache costs a ~55 min
GPU-pegged re-tune on the next render (it already happened once via a Windows cleanup tool,
TASK-022). `scripts\snapshot-caches.ps1` zips the three caches (ZLUDA ComputeCache, ~/.miopen,
~/.triton) to `F:\ml-caches\snapshots\<date>\`; `-Restore` puts the newest snapshot back.

- Snapshot right after any verified warm render; re-snapshot when the first render after a
  ComfyUI auto-git-pull runs slow (new kernels were compiled).
- Once, from an admin shell: add Defender exclusions for `F:\ComfyUI-Zluda` and both cache
  dirs (commands in the script header) - also kills the DLL false-positive/file-lock trap.
- Exclude `%LOCALAPPDATA%\ZLUDA\ComputeCache` and `%USERPROFILE%\.miopen` from any cleanup
  tools (CCleaner class).

## Known failures & fixes

| Symptom | Cause | Fix |
|---|---|---|
| llama-server dies instantly: "error: invalid argument: Projects\..." | Repo path contains a space ("Side Projects") and PS 5.1 `Start-Process -ArgumentList` does not quote args | Embed quotes around every path argument: `"-m", "``"$Root\models\file.gguf``""`. Already fixed in start-day.ps1; copy that pattern. |
| pip: NameResolutionError / ResolutionImpossible listing every version of a package | Transient DNS failure mid-install (often while big downloads saturate the link), not a real conflict | Re-run in staged groups with `--retries 10 --timeout 60`; check `Resolve-DnsName files.pythonhosted.org` first |
| ComfyUI error at VAEDecode: "GET was unable to find an engine to execute this computation" | cudnn engine selection fails on RDNA1/ZLUDA (documented fork issue) | Route the latent through `CUDNNToggleAutoPassthrough` (enable_cudnn=false) before VAEDecode - already wired in src/workers/visuals.py; keep it when editing the workflow |
| First render of a session takes 30-60 min (log shows minutes between model loads, no errors) | MIOpen/ZLUDA kernel caches were wiped (%USERPROFILE%\.miopen, %LOCALAPPDATA%\ZLUDA\ComputeCache) - Windows cleanup tools do this | It is a healthy re-tune, NOT a hang: let it run (render waiter is liveness-aware with a 75-min cap). Exclude those two cache dirs from cleanup tools |
| ComfyUI process dies silently mid-render (log just stops, no traceback) | ZLUDA/driver hard-crash class; often the same cudnn/VAE issue escalating | Check user/comfyui.log for the last op; ensure the cudnn-off node is present; if persistent, drop sampler to euler and re-test |
| Torch/ROCm build errors, silent CPU fallback | Someone tried ROCm/vLLM on gfx1010 | Don't. Vulkan/ZLUDA only. (ADR-0001) |
| OOM during image gen | Two heavy GPU stages co-resident | Serialize; unload before SDXL. (HARDWARE.md) |
| ComfyUI-Zluda stopped working after an update | Triton/flash-attn drift | Restore the venv snapshot. (STACK.md) |
| Fact-checker passes a fabricated DOI | Trusted model self-citation | Citations must be **mechanically resolved** (HTTP 200 + Crossref/OpenAlex title match) |
| Discord "file too large" on final review | 10 MB attachment cap vs ~40-60 MB master | Serve via Caddy/cloudflared link + sub-10 MB proxy |
| YouTube upload forced to private / rejected | Unverified project / quota / policy | Private-draft is by design; verify project; check quota |

## Boot-time TODOs (Phase 0)
- [x] TASK-001: llama gateway wired into start-day.ps1 (Qwen3-4B-Instruct-2507, b10092 Vulkan, 93 tok/s).
      Smoke: `python scripts/smoke_llm.py` (server must be up).
- [ ] TASK-002: real ComfyUI-Zluda launch command + venv snapshot location here.
- [x] TASK-003: Kokoro smoke: `.venv\Scripts\python scripts/smoke_tts.py` (2.8x realtime CPU, af_heart).
- [ ] TASK-006: Discord "stack ready" webhook wiring.
