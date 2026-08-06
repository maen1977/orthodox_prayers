$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$obsolete = Join-Path $root "src\SafeWindowsCleaner\MainWindow.V17.cs"
if (Test-Path $obsolete) {
    Remove-Item $obsolete -Force
    Write-Host "Removed obsolete MainWindow.V17.cs" -ForegroundColor Yellow
}

foreach ($relative in @("src\SafeWindowsCleaner\bin", "src\SafeWindowsCleaner\obj", "tests\SafeWindowsCleaner.SafetyTests\bin", "tests\SafeWindowsCleaner.SafetyTests\obj", "publish", "dist")) {
    $path = Join-Path $root $relative
    if (Test-Path $path) { Remove-Item $path -Recurse -Force }
}

& (Join-Path $root "scripts\validate-release.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Repository is clean and ready to upload to GitHub." -ForegroundColor Green
