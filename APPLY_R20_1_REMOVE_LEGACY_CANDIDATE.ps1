$ErrorActionPreference = 'Stop'
$Relative = 'data/rolling-week/candidates/2026-07-28'

$Root = (& git rev-parse --show-toplevel).Trim()
if (-not $Root) { throw 'Run this script inside the Git repository.' }
Set-Location -LiteralPath $Root

# Deleting through Git is required. A ZIP overlay cannot remove tracked files.
& git rm -r -f --ignore-unmatch -- $Relative
if ($LASTEXITCODE -ne 0) { throw "git rm failed with exit code $LASTEXITCODE" }

if (Test-Path -LiteralPath $Relative) {
    Remove-Item -LiteralPath $Relative -Recurse -Force
}

$Tracked = & git ls-files -- "$Relative/"
if ($Tracked) { throw "Legacy files are still tracked:`n$Tracked" }
if (Test-Path -LiteralPath $Relative) { throw "Legacy path still exists: $Relative" }

Write-Host "R20_1_LEGACY_CANDIDATE_REMOVED path=$Relative"
Write-Host 'R20_1_GIT_DELETION_STAGED=true'
Write-Host 'Next: git add -A; git commit -m "Remove legacy unsigned rolling candidate"; git push'
