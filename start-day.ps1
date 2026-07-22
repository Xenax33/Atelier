<#
    start-day.ps1  —  the one-click launcher for Atelier/1.

    SKELETON (Phase 0). This boots the two NATIVE GPU servers, health-gates their endpoints,
    then launches the app process, and finally pings Discord with "stack ready".

    Design rules (see docs/HARDWARE.md, docs/RUNBOOK.md):
      - GPU model servers run NATIVE Windows (never WSL2 — AMD passthrough is too weak).
      - Health-GATE every service before starting the next; never race the app ahead of the models.
      - nssm (or Task Scheduler) supervises/restarts a crashed GPU server; this script is the manual path.

    TODO(TASK-001..004): fill in real paths/commands once the servers are installed.
#>
[CmdletBinding()]
param(
    [switch]$SkipComfy,     # start without SDXL (e.g. text-only iteration)
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Wait-Endpoint {
    param([string]$Url, [int]$TimeoutSec = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

Write-Host "[atelier] boot sequence starting..." -ForegroundColor Cyan

# 1) llama.cpp Vulkan server — Qwen3-30B-A3B --cpu-moe (OpenAI-compatible on :8080)
# TODO(TASK-001): Start-Process -FilePath "<llama-server.exe>" -ArgumentList @(
#     "-m","<...>/Qwen3-30B-A3B-Q4_K_M.gguf","--cpu-moe","-c","8192","--host","127.0.0.1","--port","8080"
# ) -WindowStyle Minimized
if (-not (Wait-Endpoint -Url "http://127.0.0.1:8080/v1/models" -TimeoutSec $TimeoutSec)) {
    Write-Warning "llama.cpp gateway not up yet (expected in Phase 0 before TASK-001 is done)."
}

# 2) ComfyUI-Zluda — SDXL on :8188 (native Windows)
if (-not $SkipComfy) {
    # TODO(TASK-002): Start-Process for ComfyUI-Zluda main.py
    if (-not (Wait-Endpoint -Url "http://127.0.0.1:8188" -TimeoutSec $TimeoutSec)) {
        Write-Warning "ComfyUI-Zluda not up yet (expected before TASK-002)."
    }
}

# 3) The app (discord.py + LangGraph)
# TODO(TASK-005): & .\.venv\Scripts\python.exe -m src.main
Write-Host "[atelier] TODO: launch app process (src.main)." -ForegroundColor Yellow

# 4) Ping Discord "stack ready"
# TODO(TASK-006): post to DISCORD_CONTROL_CHANNEL_ID via webhook once services are green.
Write-Host "[atelier] boot sequence complete (skeleton)." -ForegroundColor Green
