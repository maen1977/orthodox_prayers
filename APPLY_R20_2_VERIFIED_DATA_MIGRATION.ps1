$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$required = @(
    ".github/workflows/build.yml",
    "scripts/validate_verified_data_contract.py",
    "scripts/preserve_same_day_language_lanes.py",
    "scripts/validate_workflows.py",
    "tests/test_verified_data_contract.py"
)
foreach ($path in $required) {
    if (-not (Test-Path $path)) {
        throw "Missing R20.2 file: $path. Extract the ZIP into the repository root first."
    }
}

python -m pytest -q tests/test_verified_data_contract.py tests/test_same_day_lane_preservation.py
python scripts/validate_workflows.py

Write-Host "R20.2 files verified." -ForegroundColor Green
Write-Host "Next: git add -A; commit; push; then run Actions > Rolling Week Update with mode=update once. After it succeeds, rerun Build." -ForegroundColor Yellow
