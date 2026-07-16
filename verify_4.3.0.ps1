$ErrorActionPreference = "Stop"
$gradle = Get-Content "app/build.gradle.kts" -Raw
if ($gradle -notmatch 'versionCode\s*=\s*43000') { throw "versionCode is not 43000" }
if ($gradle -notmatch 'versionName\s*=\s*"4\.3\.0"') { throw "versionName is not 4.3.0" }
python -m pytest -q
python scripts/validate_native_language_packs.py --require-complete
python scripts/validate_release_readiness.py --daily-path data/calendar/candidates/2026-07-16.json
python scripts/verify_data_signature.py
Write-Host "Orthodox Prayers 4.3.0 source checks passed." -ForegroundColor Green
