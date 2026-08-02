<#
    stop-day.ps1 - shut the whole studio down and free GPU/RAM.

    Counterpart to start-day.ps1. Closing terminal windows does NOT stop the stack:
    the bot, llama-server, and ComfyUI run as hidden background processes, and the
    pipeline deliberately restarts llama after renders. This stops everything:
      - the Discord bot (python -m src.main)
      - llama-server (frees ~4.5 GB RAM + ~5-6 GB VRAM)
      - ComfyUI-Zluda (if running)
      - the WSL VM (SearXNG; frees up to 3 GB)
#>
$ErrorActionPreference = 'SilentlyContinue'

# Disarm the watchdog FIRST so it cannot resurrect what we are about to stop.
Remove-Item (Join-Path $PSScriptRoot "state\.studio-on") -Force
Write-Host "[atelier] watchdog disarmed" -ForegroundColor Yellow

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -match "src\.main" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "[atelier] bot stopped" -ForegroundColor Yellow

Get-Process -Name "llama-server" | Stop-Process -Force
Write-Host "[atelier] llama-server stopped (GPU + RAM freed)" -ForegroundColor Yellow

Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "ComfyUI-Zluda" -and $_.Name -match "python|zluda|cmd" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "[atelier] ComfyUI stopped" -ForegroundColor Yellow

wsl --shutdown
Write-Host "[atelier] WSL VM stopped (SearXNG down)" -ForegroundColor Yellow

Write-Host "[atelier] studio is fully shut down." -ForegroundColor Green
