# 0007 — Windows-native runtime (Vulkan/ZLUDA), no dual-boot, no WSL2 for GPU
Status: Accepted
Date: 2026-07-22
_User decision (2026-07-22): "Windows-native"._

## Context
Options were Windows-native (Vulkan/ZLUDA), Linux dual-boot (ROCm), or WSL2+Docker. The GPU is gfx1010
(see ADR-0001). An NVIDIA upgrade is planned later, making heavy AMD-specific investment low-value.

## Decision
Run everything **native on Windows 11**. GPU model servers (llama.cpp Vulkan, ComfyUI-Zluda) are native
Windows processes launched by `start-day.ps1`. At v2, only the **CPU plane** (bot, Postgres, Phoenix, Caddy)
may move into Docker Compose on WSL2, reaching the native GPU servers via `host.docker.internal`.

## Consequences
- Easy: lowest-friction path; no dual-boot maintenance; matches the user's current OS.
- Hard: Windows-flavored packaging (PowerShell launcher, nssm supervision); no clean container GPU story until NVIDIA.
- Revisit when: NVIDIA upgrade (Linux/Docker+CUDA becomes attractive), or WSL2 AMD passthrough matures.

## Alternatives rejected
- **Linux dual-boot** — ~10–20% gain, fragile ROCm, extra maintenance for a soon-replaced card.
- **WSL2 GPU** — AMD passthrough too weak; GPU servers must run native regardless.
