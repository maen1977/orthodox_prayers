$ErrorActionPreference = "Stop"

$gradle = Get-Content "app/build.gradle.kts" -Raw
if ($gradle -notmatch 'versionCode\s*=\s*42000') { throw "versionCode is not 42000" }
if ($gradle -notmatch 'versionName\s*=\s*"4\.2\.0"') { throw "versionName is not 4.2.0" }

python -m json.tool canonical/daily_propers.json | Out-Null
python -m json.tool canonical/sunday_prokeimena.json | Out-Null
python -m json.tool canonical/source_native_contract.json | Out-Null
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }

Write-Host "Orthodox Prayers 4.2.0 source checks passed." -ForegroundColor Green
