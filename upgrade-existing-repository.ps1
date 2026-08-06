$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

& (Join-Path $root "remove-obsolete-v17.ps1")

foreach ($relative in @(
    "src\SafeWindowsCleaner\bin",
    "src\SafeWindowsCleaner\obj",
    "tests\SafeWindowsCleaner.SafetyTests\bin",
    "tests\SafeWindowsCleaner.SafetyTests\obj",
    "publish",
    "dist"
)) {
    $path = Join-Path $root $relative
    if (Test-Path $path) { Remove-Item $path -Recurse -Force }
}

& (Join-Path $root "scripts\validate-release.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Existing repository is cleaned and ready for: git add -A; git commit; git push" -ForegroundColor Green
