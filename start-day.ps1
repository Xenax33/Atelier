<#
    start-day.ps1  -  the one-click launcher for Atelier/1.

    SKELETON (Phase 0). This boots the two NATIVE GPU servers, health-gates their endpoints,
    then launches the app process, and finally pings Discord with "stack ready".

    Design rules (see docs/HARDWARE.md, docs/RUNBOOK.md):
      - GPU model servers run NATIVE Windows (never WSL2 - AMD passthrough is too weak).
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

# 1) llama.cpp Vulkan server - Qwen3-4B-Instruct-2507 fully in VRAM (OpenAI-compatible on :8080)
#    Measured on this box (2026-07-23, build b10092): 670 tok/s pp512, 93 tok/s tg128, FA off wins on RDNA1.
#    ADR-0011: dense small brain until the RAM upgrade; swap model here + .env when TASK-008 lands.
$llamaUp = $false
try { $llamaUp = (Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
if (-not $llamaUp) {
    # NOTE: paths under $Root contain a space ("Side Projects"); Start-Process -ArgumentList does NOT
    # quote arguments, so every path argument needs embedded quotes. (See RUNBOOK known failures.)
    Start-Process -FilePath "$Root\bin\llama-b10092\llama-server.exe" -WorkingDirectory $Root -ArgumentList @(
        "-m", "`"$Root\models\Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf`"",
        "-ngl", "99", "-c", "16384", "-fa", "off", "--jinja",
        "--host", "127.0.0.1", "--port", "8080", "--threads", "6"
    ) -WindowStyle Minimized
}
if (-not (Wait-Endpoint -Url "http://127.0.0.1:8080/health" -TimeoutSec $TimeoutSec)) {
    throw "llama.cpp gateway failed to come up on :8080 (see docs/RUNBOOK.md)."
}
Write-Host "[atelier] llama gateway healthy on :8080" -ForegroundColor Green

# 2) ComfyUI-Zluda - SDXL on :8188 (native Windows)
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
