param(
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

try {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
} catch {
    Fail "شغّل هذا الملف من داخل مستودع orthodox_prayers المحلي."
}

if (-not $repoRoot) {
    Fail "شغّل هذا الملف من داخل مستودع orthodox_prayers المحلي."
}

Set-Location $repoRoot

$remote = (& git remote get-url origin 2>$null).Trim()
if ($remote -notmatch 'maen1977[/:]orthodox_prayers(?:\.git)?$') {
    Fail "المستودع الحالي ليس maen1977/orthodox_prayers. Remote: $remote"
}

$branch = (& git branch --show-current).Trim()
if ($branch -ne "main") {
    Write-Host "Switching to main..."
    & git switch main
    if ($LASTEXITCODE -ne 0) { Fail "تعذر الانتقال إلى فرع main." }
}

Write-Host "Updating main..."
& git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { Fail "تعذر تحديث main. عالج أي تعديلات محلية أولاً." }

$path = Join-Path $repoRoot "scripts/update.py"
if (-not (Test-Path $path)) {
    Fail "الملف scripts/update.py غير موجود."
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$text = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)

$old = 'str(sources_path.relative_to(ROOT)): "المصادر والمراجع",'
$new = 'str(sources_path.relative_to(ROOT)): "data.registeredSources()",'

if ($text.Contains($new)) {
    Write-Host "Marker is already fixed." -ForegroundColor Green
} elseif ($text.Contains($old)) {
    $count = ([regex]::Matches($text, [regex]::Escape($old))).Count
    if ($count -ne 1) {
        Fail "تم العثور على العلامة القديمة $count مرات؛ أوقفت العملية للحماية."
    }

    $text = $text.Replace($old, $new)
    [System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
    Write-Host "Fixed scripts/update.py." -ForegroundColor Green
} else {
    Fail "لم أجد العلامة القديمة أو الجديدة. راجع scripts/update.py يدويًا."
}

& python -m py_compile scripts/update.py
if ($LASTEXITCODE -ne 0) { Fail "فشل فحص Python syntax." }

$sourceScreen = Join-Path $repoRoot "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SourcesScreen.java"
if (-not (Test-Path $sourceScreen)) {
    Fail "SourcesScreen.java غير موجود."
}

$sourceText = [System.IO.File]::ReadAllText($sourceScreen, [System.Text.Encoding]::UTF8)
if (-not $sourceText.Contains("data.registeredSources()")) {
    Fail "SourcesScreen.java لا يحتوي data.registeredSources()."
}

& git diff --check
if ($LASTEXITCODE -ne 0) { Fail "git diff --check فشل." }

& git add scripts/update.py
$staged = (& git diff --cached --name-only).Trim()

if ($staged) {
    & git commit -m "Fix stale SourcesScreen pipeline marker"
    if ($LASTEXITCODE -ne 0) { Fail "فشل إنشاء commit." }
} else {
    Write-Host "No new commit was needed."
}

if (-not $NoPush) {
    & git push origin main
    if ($LASTEXITCODE -ne 0) { Fail "فشل push إلى main." }
    Write-Host "Fix pushed to main." -ForegroundColor Green
} else {
    Write-Host "NoPush selected; commit was not pushed."
}

Write-Host ""
Write-Host "مهم: لا تستخدم Re-run jobs للـ Run #90." -ForegroundColor Yellow
Write-Host "ابدأ تشغيلًا جديدًا من Actions > Rolling Week Update > Run workflow."
Write-Host "Mode: update"
Write-Host "Date: 2026-07-30"
