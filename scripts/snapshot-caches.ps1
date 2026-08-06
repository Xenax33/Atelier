# snapshot-caches.ps1 - ZLUDA/MIOpen kernel-cache insurance (R&D 6.6, TASK-035).
#
# A wiped cache costs a ~55-minute GPU-pegged kernel recompile on gfx1010 (measured;
# it already happened once via a Windows cleanup tool - see RUNBOOK). A snapshot turns
# that into an unzip.
#
#   .\scripts\snapshot-caches.ps1            # snapshot the three caches to F:\ml-caches\snapshots\<date>\
#   .\scripts\snapshot-caches.ps1 -Restore   # restore the NEWEST snapshot back into place
#
# Run a snapshot right after any verified warm render (3-4 min = caches are good).
# Re-snapshot when the first render after a ComfyUI auto-git-pull runs slow (new kernels).
#
# Also recommended once, from an ADMIN PowerShell (stops Defender false-positive locks on
# ZLUDA DLLs and keeps scans off the cache churn):
#   Add-MpPreference -ExclusionPath 'F:\ComfyUI-Zluda'
#   Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\ZLUDA\ComputeCache"
#   Add-MpPreference -ExclusionPath "$env:USERPROFILE\.miopen"

param([switch]$Restore)

$ErrorActionPreference = "Stop"
$SnapRoot = "F:\ml-caches\snapshots"
$Caches = @(
    @{ Name = "zluda-computecache"; Path = Join-Path $env:LOCALAPPDATA "ZLUDA\ComputeCache" },
    @{ Name = "miopen";             Path = Join-Path $env:USERPROFILE ".miopen" },
    @{ Name = "triton";             Path = Join-Path $env:USERPROFILE ".triton" }
)

if ($Restore) {
    $latest = Get-ChildItem $SnapRoot -Directory -ErrorAction Stop |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) { throw "no snapshots found under $SnapRoot" }
    Write-Host "Restoring snapshot $($latest.Name) ..."
    foreach ($c in $Caches) {
        $zip = Join-Path $latest.FullName "$($c.Name).zip"
        if (-not (Test-Path $zip)) { Write-Host "  (no $($c.Name).zip in snapshot, skipping)"; continue }
        if (Test-Path $c.Path) { Remove-Item $c.Path -Recurse -Force }
        New-Item -ItemType Directory -Path $c.Path -Force | Out-Null
        Expand-Archive -Path $zip -DestinationPath $c.Path -Force
        Write-Host "  restored $($c.Path)"
    }
    Write-Host "Done. First render should be warm (~3-4 min); if it is slow, the stack changed since the snapshot."
    exit 0
}

$stamp = Get-Date -Format "yyyy-MM-dd"
$dest = Join-Path $SnapRoot $stamp
New-Item -ItemType Directory -Path $dest -Force | Out-Null
foreach ($c in $Caches) {
    if (-not (Test-Path $c.Path)) { Write-Host "  (no $($c.Path), skipping)"; continue }
    $zip = Join-Path $dest "$($c.Name).zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $c.Path "*") -DestinationPath $zip
    $mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host "  snapshotted $($c.Path) -> $zip ($mb MB)"
}
Write-Host "Snapshot complete: $dest"
