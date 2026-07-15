$ErrorActionPreference = "Stop"
$build = Get-Content "app/build.gradle.kts" -Raw
$coverage = Get-Content "app/src/main/java/com/orthodoxprayers/privateapp/data/TranslationCoverage.java" -Raw
$sanitizer = Get-Content "app/src/main/java/com/orthodoxprayers/privateapp/data/VerifiedContentSanitizer.java" -Raw

if ($build -notmatch 'versionCode\s*=\s*41003') { throw "versionCode is not 41003" }
if ($build -notmatch 'versionName\s*=\s*"4\.1\.3"') { throw "versionName is not 4.1.3" }
if ($coverage -notmatch 'isLocalizedTextObject') { throw "Localized metadata fix is missing" }
$firstMethod = [regex]::Match($sanitizer, 'firstUnsafeTranslationError[\s\S]*?public static void sanitize').Value
if ($firstMethod -match 'findInvalidLocalizedValue') { throw "Whole-payload localized-script rejection is still active" }
Write-Host "OK: Orthodox Prayers 4.1.3 update fix is present." -ForegroundColor Green
