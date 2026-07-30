param(
    [switch]$NoPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-WithError {
    param([string]$Message)
    Write-Host ("ERROR: " + $Message) -ForegroundColor Red
    exit 1
}

function Run-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError ("git command failed: git " + ($Arguments -join " "))
    }
}

try {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Run this script from inside the orthodox_prayers repository."
    }
    $repoRoot = $repoRoot.Trim()
}
catch {
    Stop-WithError "Run this script from inside the orthodox_prayers repository."
}

if ([string]::IsNullOrWhiteSpace($repoRoot)) {
    Stop-WithError "Could not locate the repository root."
}

Set-Location $repoRoot

$branch = (& git branch --show-current).Trim()
if ($branch -ne "main") {
    Write-Host "Switching to main..."
    Run-Git switch main
}

Write-Host "Updating main..."
Run-Git pull --ff-only origin main

$updatePath = Join-Path $repoRoot "scripts/update.py"
if (-not (Test-Path -LiteralPath $updatePath)) {
    Stop-WithError "scripts/update.py was not found."
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$text = [System.IO.File]::ReadAllText($updatePath, [System.Text.Encoding]::UTF8)

$fixedMarker = 'str(sources_path.relative_to(ROOT)): "data.registeredSources()",'

if ($text.Contains($fixedMarker)) {
    Write-Host "The R18.4 marker is already fixed." -ForegroundColor Green
}
else {
    $pattern = '(?m)^(\s*str\(sources_path\.relative_to\(ROOT\)\):\s*)"[^"]*",\s*$'
    $matches = [regex]::Matches($text, $pattern)

    if ($matches.Count -ne 1) {
        Stop-WithError ("Expected exactly one sources_path marker, but found " + $matches.Count + ".")
    }

    $replacement = $matches[0].Groups[1].Value + '"data.registeredSources()",'
    $text = $text.Remove($matches[0].Index, $matches[0].Length)
    $text = $text.Insert($matches[0].Index, $replacement)

    [System.IO.File]::WriteAllText($updatePath, $text, $utf8NoBom)
    Write-Host "Updated scripts/update.py." -ForegroundColor Green
}

Write-Host "Checking Python syntax..."
& python -m py_compile scripts/update.py
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Python syntax validation failed."
}

$sourcePath = Join-Path $repoRoot "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SourcesScreen.java"
if (-not (Test-Path -LiteralPath $sourcePath)) {
    Stop-WithError "SourcesScreen.java was not found."
}

$sourceText = [System.IO.File]::ReadAllText($sourcePath, [System.Text.Encoding]::UTF8)
if (-not $sourceText.Contains("data.registeredSources()")) {
    Stop-WithError "SourcesScreen.java does not contain data.registeredSources()."
}

& git diff --check
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "git diff --check failed."
}

Run-Git add scripts/update.py

$staged = (& git diff --cached --name-only).Trim()
if (-not [string]::IsNullOrWhiteSpace($staged)) {
    Run-Git commit -m "Fix stale SourcesScreen pipeline marker"
}
else {
    Write-Host "No new commit was needed."
}

if (-not $NoPush) {
    Run-Git push origin main
    Write-Host "The fix was pushed to main." -ForegroundColor Green
}
else {
    Write-Host "NoPush was selected. The commit was not pushed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Start a NEW Rolling Week Update workflow run."
Write-Host "Do not use Re-run jobs for run number 90."
Write-Host "Mode: update"
Write-Host "Date: 2026-07-30"
