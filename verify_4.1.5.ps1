$ErrorActionPreference = "Stop"

$gradle = Get-Content "app/build.gradle.kts" -Raw
if ($gradle -notmatch 'versionCode\s*=\s*41005') { throw "versionCode is not 41005" }
if ($gradle -notmatch 'versionName\s*=\s*"4\.1\.5"') { throw "versionName is not 4.1.5" }

python -m json.tool canonical/daily_propers.json | Out-Null
python -m json.tool canonical/sunday_prokeimena.json | Out-Null
python -m json.tool canonical/source_native_contract.json | Out-Null
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }

Write-Host "Orthodox Prayers 4.1.5 source checks passed." -ForegroundColor Green
