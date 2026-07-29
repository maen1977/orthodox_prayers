$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path
$Target = Join-Path $Root "scripts\validate_native_source_contract.py"
$Replacement = Join-Path $PSScriptRoot "validate_native_source_contract.py"

if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "Run this script from the orthodox_prayers repository root."
}

if (-not (Test-Path $Replacement)) {
    throw "Replacement validator is missing beside this script."
}

Copy-Item $Replacement $Target -Force

Write-Host "`n[1/5] Native source validator"
python scripts/validate_native_source_contract.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/5] Static protected texts"
python scripts/verify_static_texts.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/5] Full strict quality gate"
python scripts/run_quality_gate.py --strict-native-lanes
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[4/5] Git diff checks"
git diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[5/5] Commit and push"
git add scripts/validate_native_source_contract.py
git commit -m "Validate recovered native sources from embedded provenance"

if ($LASTEXITCODE -eq 0) {
    git push origin main
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "No new commit was created. Check git status."
    git status --short
}

Write-Host "`nONE_SHOT_FIX_COMPLETE"
