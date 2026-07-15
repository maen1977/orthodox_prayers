$ErrorActionPreference = "Stop"

$buildPath = Join-Path $PSScriptRoot "app/build.gradle.kts"
if (-not (Test-Path $buildPath)) { throw "Run this script from the project root." }
$build = Get-Content $buildPath -Raw
if ($build -notmatch 'versionCode\s*=\s*41004') { throw "versionCode is not 41004" }
if ($build -notmatch 'versionName\s*=\s*"4\.1\.4"') { throw "versionName is not 4.1.4" }

$required = @(
    "scripts/public_domain_scripture.py",
    "scripts/rebuild_daily_services.py",
    "tests/test_public_domain_scripture.py",
    "RELEASE_NOTES_4.1.4_AR.md"
)
foreach ($relative in $required) {
    if (-not (Test-Path (Join-Path $PSScriptRoot $relative))) { throw "Missing $relative" }
}

$update = Get-Content (Join-Path $PSScriptRoot "scripts/update.py") -Raw
if ($update -notmatch 'rebuild_daily_services\.py') { throw "Daily service recomposition is missing from update.py" }
if ($update -notmatch '--require-complete') { throw "Complete-reading publication gate is missing from update.py" }

$repository = Get-Content (Join-Path $PSScriptRoot "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java") -Raw
if ($repository -notmatch 'IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS') { throw "Android does not accept the new verified Scripture status" }

Write-Host "OK: Orthodox Prayers 4.1.4 readings fix is present." -ForegroundColor Green
