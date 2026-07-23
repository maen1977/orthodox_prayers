[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [switch]$SkipQualityGate,
    [switch]$Push
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Program,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE."
    }
}

$root = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$buildFile = Join-Path $root "app/build.gradle.kts"
$verifier = Join-Path $root "scripts/verify_r19_patch.py"
$qualityGate = Join-Path $root "scripts/run_quality_gate.py"

foreach ($required in @($buildFile, $verifier, $qualityGate)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Repository root is incorrect or R19.1 is incomplete. Missing: $required"
    }
}

$content = [System.IO.File]::ReadAllText($buildFile)
$versionCodePattern = '(?m)^([ \t]*)versionCode[ \t]*=[ \t]*\d+[ \t]*$'
$versionNamePattern = '(?m)^([ \t]*)versionName[ \t]*=[ \t]*"[^"]+"[ \t]*$'

if ([regex]::Matches($content, $versionCodePattern).Count -ne 1) {
    throw "Expected exactly one versionCode entry in app/build.gradle.kts."
}
if ([regex]::Matches($content, $versionNamePattern).Count -ne 1) {
    throw "Expected exactly one versionName entry in app/build.gradle.kts."
}

$updated = [regex]::Replace($content, $versionCodePattern, '${1}versionCode = 50015')
$updated = [regex]::Replace($updated, $versionNamePattern, '${1}versionName = "5.0.15"')

if ($updated -ne $content) {
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($buildFile, $updated, $utf8WithoutBom)
    Write-Host "BUILD_VERSION_UPDATED versionName=5.0.15 versionCode=50015"
}
else {
    Write-Host "BUILD_VERSION_ALREADY_CURRENT versionName=5.0.15 versionCode=50015"
}

$saved = [System.IO.File]::ReadAllText($buildFile)
if (
    -not $saved.Contains('versionName = "5.0.15"') -or
    -not $saved.Contains("versionCode = 50015")
) {
    throw "The build version was not written correctly."
}

$pythonCommand = Get-Command python -ErrorAction Stop
Push-Location $root
try {
    Invoke-Checked -Program $pythonCommand.Source -Arguments @(
        "scripts/verify_r19_patch.py"
    )

    if (-not $SkipQualityGate) {
        Invoke-Checked -Program $pythonCommand.Source -Arguments @(
            "scripts/run_quality_gate.py",
            "--strict-native-lanes"
        )
    }

    if ($Push) {
        $gitCommand = Get-Command git -ErrorAction Stop
        & $gitCommand.Source status --porcelain -- "app/build.gradle.kts"
        if ($LASTEXITCODE -ne 0) {
            throw "git status failed with exit code $LASTEXITCODE."
        }

        $change = (& $gitCommand.Source status --porcelain -- "app/build.gradle.kts" | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "git status failed with exit code $LASTEXITCODE."
        }

        if ($change) {
            Invoke-Checked -Program $gitCommand.Source -Arguments @(
                "add",
                "--",
                "app/build.gradle.kts"
            )
            Invoke-Checked -Program $gitCommand.Source -Arguments @(
                "commit",
                "--only",
                "-m",
                "Fix Android version for R19.1",
                "--",
                "app/build.gradle.kts"
            )
        }
        else {
            Write-Host "NO_LOCAL_BUILD_VERSION_CHANGE"
        }

        Invoke-Checked -Program $gitCommand.Source -Arguments @("push")
        Write-Host "R19_BUILD_FIX_PUSHED"
    }
    else {
        Write-Host "R19_BUILD_FIX_READY_TO_COMMIT"
        Write-Host 'Run: git add app/build.gradle.kts; git commit -m "Fix Android version for R19.1"; git push'
    }
}
finally {
    Pop-Location
}
