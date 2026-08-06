param(
    [string]$GitHubRepository = "",
    [string]$CertificatePath = "",
    [string]$CertificatePassword = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$version = "2.4.0"
$modernProject = Join-Path $PSScriptRoot "src\SafeWindowsCleaner\SafeWindowsCleaner.csproj"
$legacyProject = Join-Path $PSScriptRoot "src\SafeWindowsCleaner.Win7\SafeWindowsCleaner.Win7.csproj"
$testsProject = Join-Path $PSScriptRoot "tests\SafeWindowsCleaner.SafetyTests\SafeWindowsCleaner.SafetyTests.csproj"
$publishRoot = Join-Path $PSScriptRoot "publish"
$publishX64 = Join-Path $publishRoot "win-x64"
$publishX86 = Join-Path $publishRoot "win-x86"
$publishWin7 = Join-Path $publishRoot "win7"
$dist = Join-Path $PSScriptRoot "dist"

$packageNames = [ordered]@{
    X64Portable = "SafeWindowsCleaner-$version-Win10-11-x64-Portable.zip"
    X86Portable = "SafeWindowsCleaner-$version-Win10-11-x86-Portable.zip"
    Win7Portable = "SafeWindowsCleaner-$version-Windows7-8-8.1-Legacy-Portable.zip"
    X64Setup = "SafeWindowsCleaner-$version-Win10-11-x64-Setup.exe"
    X86Setup = "SafeWindowsCleaner-$version-Win10-11-x86-Setup.exe"
    Win7Setup = "SafeWindowsCleaner-$version-Windows7-8-8.1-Legacy-Setup.exe"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)." }
}

function Find-SignTool {
    $roots = @()
    if (${env:ProgramFiles(x86)}) { $roots += (Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin") }
    if ($env:ProgramFiles) { $roots += (Join-Path $env:ProgramFiles "Windows Kits\10\bin") }
    return $roots | Where-Object { Test-Path $_ } | ForEach-Object {
        Get-ChildItem $_ -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' }
    } | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}

function Find-InnoCompiler {
    $roots = @(${env:ProgramFiles(x86)}, $env:ProgramFiles) | Where-Object { $_ -and (Test-Path $_) }
    return $roots | ForEach-Object {
        Get-ChildItem $_ -Filter ISCC.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match 'Inno Setup [67]\\ISCC\.exe$' }
    } | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}

function Sign-And-Verify {
    param([string]$Path, [string]$SignTool)
    & $SignTool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $CertificatePath /p $CertificatePassword $Path
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $Path" }
    & $SignTool verify /pa /v $Path
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $Path" }
}

function Test-ModernSetup {
    param([string]$SetupPath, [string]$Suffix)

    $installDir = Join-Path $env:TEMP "SafeWindowsCleaner-$Suffix-Smoke"
    $installLog = Join-Path $env:TEMP "SafeWindowsCleaner-$Suffix-install.log"
    Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue

    $args = @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCANCEL",
        "/LANG=en", "/DIR=`"$installDir`"", "/LOG=`"$installLog`""
    )
    $install = Start-Process -FilePath $SetupPath -ArgumentList $args -PassThru
    if (-not $install.WaitForExit(180000)) {
        Stop-Process -Id $install.Id -Force -ErrorAction SilentlyContinue
        if (Test-Path $installLog) { Get-Content $installLog | Select-Object -Last 120 }
        throw "$Suffix Setup installation exceeded 3 minutes."
    }
    if ($install.ExitCode -ne 0) {
        if (Test-Path $installLog) { Get-Content $installLog | Select-Object -Last 120 }
        throw "$Suffix Setup installation failed with exit code $($install.ExitCode)."
    }

    $installedExe = Join-Path $installDir "SafeWindowsCleaner.exe"
    if (-not (Test-Path $installedExe)) { throw "$Suffix Setup did not install SafeWindowsCleaner.exe." }

    $uninstaller = Get-ChildItem $installDir -Filter "unins*.exe" -File | Select-Object -First 1
    if (-not $uninstaller) { throw "$Suffix Setup did not create an uninstaller." }
    $uninstall = Start-Process -FilePath $uninstaller.FullName -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -PassThru
    if (-not $uninstall.WaitForExit(180000)) {
        Stop-Process -Id $uninstall.Id -Force -ErrorAction SilentlyContinue
        Get-Process SafeWindowsCleaner -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        throw "$Suffix Setup uninstall exceeded 3 minutes."
    }
    if ($uninstall.ExitCode -ne 0) { throw "$Suffix Setup uninstall failed with exit code $($uninstall.ExitCode)." }
    if (Test-Path $installDir) { throw "$Suffix uninstall left the installation directory behind." }
}

& (Join-Path $PSScriptRoot "scripts\validate-release.ps1")
if ($LASTEXITCODE -ne 0) { throw "Release configuration validation failed." }

Write-Host "Building Safe Windows Cleaner Lite $version multi-OS release..." -ForegroundColor Cyan
Write-Host "Modern: Windows 10/11 x64 + x86 | Legacy: Windows 7 SP1 / 8 / 8.1 x86/x64" -ForegroundColor DarkCyan

Remove-Item $publishRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $publishX64, $publishX86, $publishWin7, $dist -Force | Out-Null

$repositoryProperty = @()
if (-not [string]::IsNullOrWhiteSpace($GitHubRepository)) {
    $repositoryProperty += "-p:GitHubRepository=$GitHubRepository"
}

Invoke-Checked dotnet @("restore", $modernProject) "Modern application restore failed"
Invoke-Checked dotnet @("restore", $testsProject) "Safety-test restore failed"
Invoke-Checked dotnet @("restore", $legacyProject) "Windows Legacy restore failed"
Invoke-Checked dotnet (@("build", $modernProject, "--configuration", "Release", "--no-restore") + $repositoryProperty) "Modern application build failed"
Invoke-Checked dotnet (@("build", $testsProject, "--configuration", "Release", "--no-restore") + $repositoryProperty) "Safety-test build failed"
Invoke-Checked dotnet @("run", "--project", $testsProject, "--configuration", "Release", "--no-build") "Windows safety tests failed"
Invoke-Checked dotnet @("build", $legacyProject, "--configuration", "Release", "--no-restore", "-p:ContinuousIntegrationBuild=true") "Windows Legacy build failed"

foreach ($rid in @("win-x64", "win-x86")) {
    Invoke-Checked dotnet @("restore", $modernProject, "--runtime", $rid, "-p:SelfContained=true") "Runtime restore failed for $rid"
    $output = if ($rid -eq "win-x64") { $publishX64 } else { $publishX86 }
    $publishArgs = @(
        "publish", $modernProject,
        "--configuration", "Release",
        "--runtime", $rid,
        "--self-contained", "true",
        "--no-restore",
        "-p:PublishSingleFile=false",
        "-p:IncludeNativeLibrariesForSelfExtract=false",
        "-p:EnableCompressionInSingleFile=false",
        "--output", $output
    ) + $repositoryProperty
    Invoke-Checked dotnet $publishArgs "Publish failed for $rid"
    Copy-Item (Join-Path $PSScriptRoot "PACKAGE-SELECTION-AR-EN.txt") (Join-Path $output "PACKAGE-SELECTION-AR-EN.txt") -Force
}

$legacyBin = Join-Path $PSScriptRoot "src\SafeWindowsCleaner.Win7\bin\Release\net461"
$legacyExe = Join-Path $legacyBin "SafeWindowsCleaner.exe"
if (-not (Test-Path $legacyExe)) { throw "Windows Legacy executable was not produced." }
Copy-Item (Join-Path $legacyBin "*") $publishWin7 -Recurse -Force
Copy-Item (Join-Path $PSScriptRoot "WINDOWS7-LEGACY-README-AR-EN.txt") (Join-Path $publishWin7 "WINDOWS7-LEGACY-README-AR-EN.txt") -Force
Copy-Item (Join-Path $PSScriptRoot "PACKAGE-SELECTION-AR-EN.txt") (Join-Path $publishWin7 "PACKAGE-SELECTION-AR-EN.txt") -Force

$signed = $false
$signtool = $null
if (-not [string]::IsNullOrWhiteSpace($CertificatePath)) {
    if (-not (Test-Path $CertificatePath)) { throw "Signing certificate was not found: $CertificatePath" }
    if ([string]::IsNullOrWhiteSpace($CertificatePassword)) { throw "CertificatePassword is required for signing." }
    $signtool = Find-SignTool
    if (-not $signtool) { throw "signtool.exe x64 was not found. Install the Windows SDK." }
    foreach ($exe in @(
        (Join-Path $publishX64 "SafeWindowsCleaner.exe"),
        (Join-Path $publishX86 "SafeWindowsCleaner.exe"),
        (Join-Path $publishWin7 "SafeWindowsCleaner.exe")
    )) {
        Sign-And-Verify $exe $signtool
    }
    $signed = $true
} else {
    Write-Warning "No certificate was supplied. Outputs will be unsigned and may trigger SmartScreen."
}

Compress-Archive -Path (Join-Path $publishX64 "*") -DestinationPath (Join-Path $dist $packageNames.X64Portable) -Force
Compress-Archive -Path (Join-Path $publishX86 "*") -DestinationPath (Join-Path $dist $packageNames.X86Portable) -Force
Compress-Archive -Path (Join-Path $publishWin7 "*") -DestinationPath (Join-Path $dist $packageNames.Win7Portable) -Force

$iscc = Find-InnoCompiler
if (-not $iscc) { throw "Inno Setup 6 or 7 is required to build the three Setup packages." }
Write-Host "Using Inno Setup compiler: $iscc" -ForegroundColor DarkCyan
foreach ($installerScript in @(
    "installer\SafeWindowsCleaner.iss",
    "installer\SafeWindowsCleaner.x86.iss",
    "installer\SafeWindowsCleaner.Win7.iss"
)) {
    Invoke-Checked $iscc @((Join-Path $PSScriptRoot $installerScript)) "Inno Setup compilation failed for $installerScript"
}

foreach ($name in @($packageNames.X64Setup, $packageNames.X86Setup, $packageNames.Win7Setup)) {
    if (-not (Test-Path (Join-Path $dist $name))) { throw "Expected Setup package was not produced: $name" }
}

Test-ModernSetup (Join-Path $dist $packageNames.X64Setup) "x64"
Test-ModernSetup (Join-Path $dist $packageNames.X86Setup) "x86"
Write-Host "Windows Legacy Setup is compile-validated only; its OS gate intentionally blocks the current Windows 10/11 build machine." -ForegroundColor Yellow

if ($signed) {
    foreach ($setup in @($packageNames.X64Setup, $packageNames.X86Setup, $packageNames.Win7Setup)) {
        Sign-And-Verify (Join-Path $dist $setup) $signtool
    }
}

$allPackages = @(
    $packageNames.X64Portable, $packageNames.X86Portable, $packageNames.Win7Portable,
    $packageNames.X64Setup, $packageNames.X86Setup, $packageNames.Win7Setup
)
foreach ($name in $allPackages) {
    $file = Join-Path $dist $name
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $name" | Set-Content "$file.sha256" -Encoding ascii
}

@(
    "Publisher: معن حنونة للستلايت",
    "Phone: 00962788272988",
    "Version: $version",
    "Modern packages: Windows 10/11 x64 and x86, .NET 8 self-contained",
    "Legacy package: Windows 7 SP1 / 8 / 8.1 x86/x64, .NET Framework 4.6.1 or later required",
    "Virtual memory: adaptive reversible 4/8/16 GB preset",
    "Signed: $signed"
) | Set-Content (Join-Path $dist "BUILD-INFO.txt") -Encoding utf8

Write-Host "Created six packages in: $dist" -ForegroundColor Green
$allPackages | ForEach-Object { Write-Host " - $_" -ForegroundColor Green }
Write-Host "Signed: $signed" -ForegroundColor Green
