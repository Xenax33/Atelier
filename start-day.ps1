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
    [switch]$WithComfy,     # ALSO boot ComfyUI-Zluda. Default off: the 8GB card cannot hold the
                            # brain AND SDXL at once (HARDWARE.md); the render worker starts/stops
                            # ComfyUI around visual stages instead.
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

# 1.5) SearXNG (researcher search backend) in WSL2 Ubuntu + docker.
#      CRITICAL QUIRK: the WSL VM terminates when the last wsl.exe session exits, killing the
#      containers. The "sleep infinity" session below is the keepalive that holds the VM open.
$searxUp = $false
try { $searxUp = (Invoke-WebRequest -Uri "http://127.0.0.1:8888/healthz" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
if (-not $searxUp) {
    Start-Process -FilePath "wsl.exe" -WindowStyle Hidden -ArgumentList @(
        "-d", "Ubuntu", "-u", "root", "-e", "sh", "-c",
        "service docker start; cd /opt/searxng && docker compose up -d; exec sleep infinity"
    )
    if (Wait-Endpoint -Url "http://127.0.0.1:8888/healthz" -TimeoutSec 90) {
        Write-Host "[atelier] SearXNG healthy on :8888" -ForegroundColor Green
    } else {
        Write-Warning "SearXNG did not come up (researcher falls back to direct APIs)."
    }
} else {
    Write-Host "[atelier] SearXNG already healthy on :8888" -ForegroundColor Green
}

# 2) ComfyUI-Zluda - SDXL on :8188 (native Windows, lives at F:\ComfyUI-Zluda - no spaces in path).
#    Measured (2026-07-25): first-ever run ~55 min one-time kernel compile; warm renders 3.0 min at
#    768x1344. Opt-in here (see param note); the pipeline's render worker manages it per-stage.
if ($WithComfy) {
    $comfyUp = $false
    try { $comfyUp = (Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
    if (-not $comfyUp) {
        # NOTE: invoke the bat by FULL path (bare names misresolve in some shells; see RUNBOOK).
        Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "cd /d F:\ComfyUI-Zluda && F:\ComfyUI-Zluda\comfyui-n.bat") -WindowStyle Minimized
    }
    if (-not (Wait-Endpoint -Url "http://127.0.0.1:8188/system_stats" -TimeoutSec 300)) {
        Write-Warning "ComfyUI-Zluda failed to come up on :8188 (see docs/SETUP-COMFYUI.md)."
    } else {
        Write-Host "[atelier] ComfyUI-Zluda healthy on :8188" -ForegroundColor Green
    }
}

# 3) The app (Discord control plane; later + LangGraph)
$envFile = "$Root\.env"
$envReady = (Test-Path $envFile) -and -not (Select-String -Path $envFile -Pattern "^DISCORD_BOT_TOKEN=changeme" -Quiet)
if ($envReady) {
    $botRunning = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match "src\.main" }
    if (-not $botRunning) {
        Start-Process -FilePath "$Root\.venv\Scripts\python.exe" -WorkingDirectory $Root -ArgumentList @("-m", "src.main") -WindowStyle Minimized
        Write-Host "[atelier] app (Discord bot) launching..." -ForegroundColor Green
    } else {
        Write-Host "[atelier] app already running." -ForegroundColor Green
    }
} else {
    Write-Host "[atelier] .env missing or DISCORD_BOT_TOKEN unset: app not launched (see .env.example)." -ForegroundColor Yellow
}

# 4) Ping Discord "stack ready"
# TODO(TASK-006): post to DISCORD_CONTROL_CHANNEL_ID via webhook once services are green.
Write-Host "[atelier] boot sequence complete (skeleton)." -ForegroundColor Green
