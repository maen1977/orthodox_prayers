param(
    [string]$Repository = "maen1977/orthodox_prayers",
    [string]$Alias = "orthodox-prayers-release"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install it and run this script again."
    }
}

function New-RandomSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($buffer)).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function SecureToPlain([string]$Encrypted) {
    $secure = ConvertTo-SecureString $Encrypted
    return [System.Net.NetworkCredential]::new('', $secure).Password
}

Require-Command "gh"
Require-Command "keytool"

Write-Host "Checking GitHub authentication..."
& gh auth status | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run: gh auth login"
}

$root = Split-Path -Parent $PSScriptRoot
$signingDir = Join-Path $root ".release-signing"
$keystore = Join-Path $signingDir "orthodox-prayers-release.jks"
$backup = Join-Path $signingDir "release-signing.dpapi.json"
New-Item -ItemType Directory -Path $signingDir -Force | Out-Null

if ((Test-Path $keystore) -xor (Test-Path $backup)) {
    throw "Signing backup is incomplete. Both the keystore and release-signing.dpapi.json must exist together. Do not generate a replacement key for an already released app."
}

if (-not (Test-Path $keystore)) {
    $storePassword = New-RandomSecret
    $keyPassword = $storePassword
    Write-Host "Creating a permanent Android release key..."
    & keytool -genkeypair -v `
        -keystore $keystore `
        -storetype JKS `
        -alias $Alias `
        -keyalg RSA `
        -keysize 4096 `
        -validity 10000 `
        -storepass $storePassword `
        -keypass $keyPassword `
        -dname "CN=Orthodox Prayers, OU=Release, O=Orthodox Prayers, L=Amman, C=JO"
    if ($LASTEXITCODE -ne 0) { throw "keytool failed to create the release keystore." }

    $storeProtected = ConvertFrom-SecureString (ConvertTo-SecureString $storePassword -AsPlainText -Force)
    $keyProtected = ConvertFrom-SecureString (ConvertTo-SecureString $keyPassword -AsPlainText -Force)
    @{
        repository = $Repository
        alias = $Alias
        storePasswordDpapi = $storeProtected
        keyPasswordDpapi = $keyProtected
        createdUtc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -Path $backup -Encoding UTF8
    Write-Host "Permanent release key created. Back up the .release-signing folder securely and never delete it."
} else {
    $state = Get-Content $backup -Raw | ConvertFrom-Json
    if ($state.alias -ne $Alias) {
        throw "Alias mismatch. Existing key uses '$($state.alias)', requested '$Alias'."
    }
    $storePassword = SecureToPlain $state.storePasswordDpapi
    $keyPassword = SecureToPlain $state.keyPasswordDpapi
    Write-Host "Reusing the existing permanent release key."
}

$keystoreBytes = [IO.File]::ReadAllBytes($keystore)
$keystoreB64 = [Convert]::ToBase64String($keystoreBytes)

Write-Host "Uploading encrypted release secrets to GitHub Actions..."
& gh secret set ANDROID_KEYSTORE_B64 --repo $Repository --body $keystoreB64
if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEYSTORE_B64." }
& gh secret set ANDROID_KEYSTORE_PASSWORD --repo $Repository --body $storePassword
if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEYSTORE_PASSWORD." }
& gh secret set ANDROID_KEY_ALIAS --repo $Repository --body $Alias
if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEY_ALIAS." }
& gh secret set ANDROID_KEY_PASSWORD --repo $Repository --body $keyPassword
if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEY_PASSWORD." }

Write-Host "RELEASE_SIGNING_SETUP_OK repository=$Repository alias=$Alias"
Write-Host "Next: GitHub > Actions > Build Church Prayers > Run workflow > enable 'Publish a signed GitHub Release for the current version'."
Write-Host "Important: keep the .release-signing folder backed up. Losing this key means future APKs cannot update installed production copies."
