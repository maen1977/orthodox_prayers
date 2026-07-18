param(
    [string]$RepositoryPath = "."
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $RepositoryPath).Path
$calendarDir = Join-Path $root "data/calendar"
$todayPath = Join-Path $calendarDir "today.json"

if (-not (Test-Path $todayPath)) {
    throw "Missing required file: $todayPath"
}

$today = Get-Content -Raw -Encoding UTF8 $todayPath | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($today.date_iso)) {
    throw "data/calendar/today.json has no valid date_iso"
}

$keep = @(
    "today.json",
    "today.json.sig",
    "$($today.date_iso).json",
    "$($today.date_iso).json.sig"
)

$removed = 0
Get-ChildItem -Path $calendarDir -File | Where-Object {
    ($_.Name -like "*.json" -or $_.Name -like "*.json.sig") -and ($keep -notcontains $_.Name)
} | ForEach-Object {
    Write-Host "REMOVED data/calendar/$($_.Name)"
    Remove-Item -LiteralPath $_.FullName -Force
    $removed++
}

Write-Host "CALENDAR_CLEAN_OK date=$($today.date_iso) removed=$removed"
Write-Host "Now run: python scripts/run_quality_gate.py --strict-native-lanes"
