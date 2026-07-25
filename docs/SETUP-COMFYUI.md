# ComfyUI-Zluda setup for the RX 5700 XT (gfx1010) - verified 2026-07-25

> **STATUS: COMPLETE AND WORKING (2026-07-25).** First 768x1344 SDXL image rendered after ~55 min of
> one-time ZLUDA/MIOpen kernel compilation; second image took **3.0 minutes** (the real steady-state
> cost). Venv snapshotted to `F:\ComfyUI-Zluda\venv-snapshot-2026-07-25.zip`, package list in
> `docs/zluda-venv-freeze-2026-07-25.txt`. Extra traps hit during install (beyond the list below):
> (1) the installer's own zluda.zip download failed silently via a Defender file-lock - re-download and
> extract with a settle delay + retries, then re-copy the 5 DLLs into `venv\...\torch\lib` per
> install-n.bat lines 128-136; (2) pip resolved a numpy-2-built scipy against the pinned numpy 1.26.4
> (crash: "module 'numpy' has no attribute 'long'") - fix `pip install scipy==1.13.1` in the Comfy venv.

The visuals engine (TASK-002). Every step below was verified against current sources on 2026-07-25
(patientx/ComfyUI-Zluda README + install-n.bat read verbatim, likelovewant rocBLAS release checked live).
If this doc and the fork's README disagree in the future, re-verify: this stack moves fast.

## Layout decision

- ComfyUI-Zluda lives at **`F:\ComfyUI-Zluda`** - OUTSIDE the repo, because the fork requires a path
  without spaces and our repo lives under "F:\Side Projects" (a space that already bit us once).
- Model weights stay in the repo tree at `models/sdxl/{checkpoints,vae}/` and are wired in via
  `extra_model_paths.yaml` (so ComfyUI upgrades never touch our weights).

## State of this box (checked 2026-07-25)

| Prerequisite | Status |
|---|---|
| VS Build Tools 2022 + C++ workload | ALREADY INSTALLED |
| VC++ x64 runtime | ALREADY INSTALLED |
| Adrenalin driver >= 25.5.1 (required by this path) | OK (2026-06 driver) |
| Python 3.12 (python.org build) | OK - the fork supports 3.11/3.12 (NOT 3.13) |
| AMD HIP SDK 6.2.4 | **MISSING - manual admin install (step 1)** |
| gfx1010 rocBLAS + ZLUDA extension files | staged in `%USERPROFILE%\Downloads\atelier-comfyui-setup\` |

## Key facts (so nobody relitigates them)

- **HIP SDK version for gfx1010 is 6.2.4** - not 5.7.1 (old guides; pre-RDNA cards only, conflicts with
  current drivers) and NOT 7.x (unsupported by ZLUDA tooling).
- gfx1010 is not officially supported by the HIP SDK -> needs **community rocBLAS libraries**
  (likelovewant ROCmLibs v0.6.2.4, file `rocm.gfx1010-gfx1012-for.hip.sdk.6.2.4.7z`).
- **Python 3.12 is fine; Triton is NOT needed for plain SDXL** (the old "pin Triton 3.0.0 + flash-attn
  wheel" advice is obsolete; flash-attn is dead code in install-n.bat; default attention is
  `--use-quad-cross-attention` which is the stable choice on RDNA1). If the installer's Triton phase
  errors hard, use `install-legacy.bat`.
- Torch is pinned by the installer: 2.7.0 cu118 + ZLUDA 3.9.5 nightly DLL patch. numpy 1.26.4.
- **First generation compiles for 10-15+ minutes** (ZLUDA per-model compile). Do not kill it.
  Caches: `%LOCALAPPDATA%\ZLUDA\ComputeCache`, `~\.miopen`, `~\.triton` (cache-clean.bat clears).
- Known RDNA1 failure modes: VAE-decode `GET/FIND unable to find an engine` -> CFZ CUDNN Toggle node
  (enable_cudnn=False); `miopenStatusUnknownError` at VAE decode -> use TILED VAE decode (plan on it
  at 768x1344 on 8 GB); xformers does not work with ZLUDA - avoid nodes that require it.
- Launch = `comfyui-user.bat` (update-safe copy of comfyui-n.bat), port 8188, auto-git-pulls each start.
- Fallbacks, in order: (1) patientx-cfz/comfyui-rocm (official-ROCm route, RDNA1 since ~2026-06,
  maintainer-untested on RDNA1); (2) `--directml` (works but 2-4x slower + VRAM-hungry; smoke-test only).

## Manual admin steps (user, ~15 min + one restart)

Staged files are in `%USERPROFILE%\Downloads\atelier-comfyui-setup\`.

1. **Install AMD HIP SDK 6.2.4**: download "Windows 10 & 11 6.2.4 HIP SDK" from
   https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html and run it (defaults; installs to
   `C:\Program Files\AMD\ROCm\6.2\`).
   **TRAP (hit 2026-07-25):** AMD's page front-loads the NEWEST SDK. The file you want is the
   **24.Q4** release = HIP 6.2.4 (`AMD-Software-PRO-Edition-24.Q4-Win10-Win11-For-HIP.exe`, direct:
   https://download.amd.com/developer/eula/rocm-hub/AMD-Software-PRO-Edition-24.Q4-Win10-Win11-For-HIP.exe ).
   The `25.Q3` file is HIP **6.4** (RX 6800+ only) and installs to `ROCm\6.4` - wrong for gfx1010. If 6.4
   got installed by accident: leave it (versions coexist; our tooling targets `6.2` explicitly), just also
   install 6.2.4. After ANY of these PRO installers, re-check the display driver version - the PRO
   edition can replace the consumer Adrenalin driver, and ZLUDA needs Adrenalin >= 25.5.1.
2. **System env vars** (if the installer did not set them): `HIP_PATH` and `HIP_PATH_62` =
   `C:\Program Files\AMD\ROCm\6.2\` ; append `C:\Program Files\AMD\ROCm\6.2\bin` to system PATH.
3. **ZLUDA HIP-SDK extension**: extract `HIP-SDK-extension-zluda395.zip` INTO
   `C:\Program Files\AMD\ROCm\6.2` (overwrite). (If the staged zip is missing, download from the link in
   the fork's README, section "HIP SDK addon".)
4. **gfx1010 rocBLAS swap**: back up `C:\Program Files\AMD\ROCm\6.2\bin\rocblas\library`, then extract
   `rocm-gfx1010-hip624.7z` (use staged `7zr.exe`: `7zr.exe x rocm-gfx1010-hip624.7z`) and overwrite the
   `library` folder; if the archive contains `rocblas.dll`, copy it to `...\6.2\bin`.
5. Optional but recommended: add a Windows Defender exclusion for `F:\ComfyUI-Zluda`
   (zluda.exe/nccl.dll false positives are documented).
6. **Restart Windows.**

## Automated steps (agent, after the restart)

7. `cd F:\ComfyUI-Zluda && install-n.bat` (creates venv, torch-cu118, ZLUDA patch; ~10-20 min).
8. Copy `extra_model_paths.yaml.example` -> `extra_model_paths.yaml`, point the `comfyui:` block at
   `F:/Side Projects/atelier/models/sdxl/` with `checkpoints: checkpoints/`, `vae: vae/`.
9. Launch `comfyui-user.bat`, wait through the first-run compile, render one 768x1344 SDXL image
   (tiled VAE decode), and measure seconds/image.
10. **SNAPSHOT the venv immediately** (`F:\ComfyUI-Zluda\venv` -> zip stored outside git) and record the
    exact torch/zluda versions here + STACK.md. Then mark TASK-002 done in the ledger.
