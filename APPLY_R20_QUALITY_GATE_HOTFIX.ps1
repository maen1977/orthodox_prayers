$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Legacy = Join-Path $Root 'data/rolling-week/candidates/2026-07-28'

if (Test-Path -LiteralPath $Legacy) {
    Remove-Item -LiteralPath $Legacy -Recurse -Force
    Write-Host 'REMOVED_LEGACY_UNSIGNED_CANDIDATE path=data/rolling-week/candidates/2026-07-28'
} else {
    Write-Host 'LEGACY_UNSIGNED_CANDIDATE_ABSENT path=data/rolling-week/candidates/2026-07-28'
}

$Candidates = Join-Path $Root 'data/rolling-week/candidates'
if ((Test-Path -LiteralPath $Candidates) -and -not (Get-ChildItem -LiteralPath $Candidates -Force)) {
    Remove-Item -LiteralPath $Candidates -Force
}

Write-Host 'R20_QUALITY_GATE_HOTFIX_APPLIED'
