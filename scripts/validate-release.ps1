param(
    [string]$ExpectedVersion = "2.4.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Text([string]$RelativePath) {
    $path = Join-Path $root $RelativePath
    Assert-True (Test-Path $path) "Required file is missing: $RelativePath"
    return Get-Content $path -Raw
}

$modernProjectPath = Join-Path $root "src\SafeWindowsCleaner\SafeWindowsCleaner.csproj"
$legacyProjectPath = Join-Path $root "src\SafeWindowsCleaner.Win7\SafeWindowsCleaner.Win7.csproj"
[xml]$modernProject = Get-Content $modernProjectPath -Raw
[xml]$legacyProject = Get-Content $legacyProjectPath -Raw
Assert-True ([string]$modernProject.Project.PropertyGroup.Version -eq $ExpectedVersion) "Modern project version does not match $ExpectedVersion."
Assert-True ([string]$modernProject.Project.PropertyGroup.TargetFramework -eq "net8.0-windows") "Modern project must target net8.0-windows."
Assert-True ([string]$legacyProject.Project.PropertyGroup.Version -eq $ExpectedVersion) "Windows 7/8/8.1 project version does not match $ExpectedVersion."
Assert-True ([string]$legacyProject.Project.PropertyGroup.TargetFramework -eq "net461") "Windows Legacy project must target .NET Framework 4.6.1."
Assert-True ([string]$legacyProject.Project.PropertyGroup.PlatformTarget -eq "AnyCPU") "Windows Legacy project must support both 32-bit and 64-bit Windows 7/8/8.1."
Assert-True ([string]$legacyProject.Project.PropertyGroup.AssemblyName -eq "SafeWindowsCleaner") "Legacy output must keep the same executable identity as the modern application."

$modernManifest = Read-Text "src\SafeWindowsCleaner\app.manifest"
$legacyManifest = Read-Text "src\SafeWindowsCleaner.Win7\app.manifest"
foreach ($manifest in @($modernManifest, $legacyManifest)) {
    Assert-True ($manifest -match 'requestedExecutionLevel\s+level="requireAdministrator"') "Every application package must request administrator privileges."
}
Assert-True ($modernManifest -match ('version="' + [regex]::Escape($ExpectedVersion) + '\.0"')) "Modern manifest version is inconsistent."
Assert-True ($legacyManifest -match ('version="' + [regex]::Escape($ExpectedVersion) + '\.0"')) "Windows 7/8/8.1 manifest version is inconsistent."

$installerX64 = Read-Text "installer\SafeWindowsCleaner.iss"
$installerX86 = Read-Text "installer\SafeWindowsCleaner.x86.iss"
$installerWin7 = Read-Text "installer\SafeWindowsCleaner.Win7.iss"
$installers = @($installerX64, $installerX86, $installerWin7)
$commonAppId = 'AppId=\{\{CE435A11-66CC-4B7E-A669-F45DCE612BB4\}'
foreach ($installer in $installers) {
    Assert-True ($installer -match ('#define MyAppVersion "' + [regex]::Escape($ExpectedVersion) + '"')) "An installer version is inconsistent."
    Assert-True ($installer -match $commonAppId) "All packages must share one application identity so upgrades replace old copies."
    Assert-True ($installer -match 'DefaultDirName=\{autopf\}\\Safe Windows Cleaner Lite') "All packages must share the same installation directory."
    Assert-True ($installer -match '#define MyAppExeName "SafeWindowsCleaner\.exe"') "All packages must install the same executable name."
    Assert-True ($installer -match 'OutputBaseFilename=\{#MyPackageName\}-Setup') "An installer does not use its audited package-name macro."
    Assert-True ($installer -match 'PrivilegesRequired=admin') "Every installer must require administrator privileges."
    Assert-True ($installer -match 'postinstall[^\r\n]*runascurrentuser') "Post-install launch must explicitly use Setup's elevated token to avoid CreateProcess error 740."
    Assert-True ($installer -notmatch '\brunasoriginaluser\b') "An installer contains runasoriginaluser."
    Assert-True ($installer -notmatch '\bignoreerrors\b') "An installer contains unsupported Inno Setup flag ignoreerrors."
    Assert-True ($installer -match '\[InstallDelete\]') "Upgrade replacement cleanup is missing."
    Assert-True ($installer -match '\[UninstallDelete\]') "Complete uninstall cleanup is missing."
    Assert-True ($installer -match 'taskkill /F /IM \{#MyAppExeName\}') "Old running copies are not closed before upgrade."
    foreach ($language in @("en", "ar")) {
        Assert-True ($installer -match ('Name: "' + $language + '"; MessagesFile:')) "Installer language '$language' is missing."
    }
    foreach ($language in @("es", "fr", "it", "ru", "de", "pt")) {
        Assert-True ($installer -notmatch ('Name: "' + $language + '"; MessagesFile:')) "Incomplete installer language '$language' is exposed."
    }
}
Assert-True ($installerX64 -match 'Source: "\.\.\publish\win-x64\\\*"') "x64 installer is not connected to the x64 publish output."
Assert-True ($installerX64 -match 'ArchitecturesAllowed=x64compatible') "x64 architecture detection is missing."
Assert-True ($installerX64 -match 'MinVersion=10\.0') "x64 package must require Windows 10 or newer."
Assert-True ($installerX64 -match '#define MyPackageName "SafeWindowsCleaner-2\.4\.0-Win10-11-x64"') "x64 package filename is unclear."
Assert-True ($installerX86 -match 'Source: "\.\.\publish\win-x86\\\*"') "x86 installer is not connected to the x86 publish output."
Assert-True ($installerX86 -match 'ArchitecturesAllowed=x86compatible') "x86 architecture detection is missing."
Assert-True ($installerX86 -match 'MinVersion=10\.0') "x86 package must require Windows 10 or newer."
Assert-True ($installerX86 -match '#define MyPackageName "SafeWindowsCleaner-2\.4\.0-Win10-11-x86"') "x86 package filename is unclear."
Assert-True ($installerWin7 -match 'Source: "\.\.\publish\win7\\\*"') "Windows 7/8/8.1 installer is not connected to the Legacy publish output."
Assert-True ($installerWin7 -match 'MinVersion=6\.1sp1') "Windows 7 SP1 minimum version check is missing."
Assert-True ($installerWin7 -match 'OnlyBelowVersion=10\.0') "Windows Legacy package must not install on Windows 10 or newer."
Assert-True ($installerWin7 -match 'Net461MinimumRelease\s*=\s*394254') ".NET Framework 4.6.1 or later prerequisite detection is missing."
Assert-True ($installerWin7 -match '#define MyPackageName "SafeWindowsCleaner-2\.4\.0-Windows7-8-8.1-Legacy"') "Windows 7/8/8.1 package filename is unclear."

Assert-True ($installerWin7 -match 'en.WindowsVersionNotSupported=.*Windows 7 SP1, Windows 8, and Windows 8\.1') "Legacy OS guidance is incomplete."
Assert-True ($installerWin7 -match 'IsDotNet461OrLaterInstalled') "Legacy .NET prerequisite function is missing."

$arInstallerLanguage = Read-Text "installer\Languages\Arabic.isl"
Assert-True ($arInstallerLanguage -match 'RightToLeft=yes') "Arabic Setup must use right-to-left layout."

$localizationService = Read-Text "src\SafeWindowsCleaner\Services\LocalizationService.cs"
$localizationCatalog = Read-Text "src\SafeWindowsCleaner\Services\LocalizationCatalog.cs"
Assert-True ($localizationService -match 'GetLanguageDisplayOptions') "Localized language display labels are missing."
Assert-True ($localizationService -match 'ContainsEnglishSizeUnit\(entry\.Ar\)') "Arabic catalog size-unit validation is missing."
Assert-True ($localizationService -match 'ContainsArabicSizeUnit\(entry\.En\)') "English catalog size-unit validation is missing."
Assert-True ($localizationCatalog -match 'record LocalizedEntry\(string Key, string Ar, string En\)') "Production localization must contain exactly Arabic and English."
Assert-True ($localizationCatalog -notmatch 'string (Es|Fr|It|Ru|De|Pt)\b') "Retired language fields remain compiled."
$mainWindowXaml = Read-Text "src\SafeWindowsCleaner\MainWindow.xaml"
$languageWindowXaml = Read-Text "src\SafeWindowsCleaner\LanguageSelectionWindow.xaml"
Assert-True ($mainWindowXaml -match 'LanguageComboBox[\s\S]*?DisplayMemberPath="DisplayName"') "Settings language selector must use localized display names."
Assert-True ($mainWindowXaml -notmatch 'DisplayMemberPath="NativeName"') "Settings language selector still mixes native names."
Assert-True ($languageWindowXaml -match 'Text="\{Binding DisplayName\}"') "First-run language selector must use one interface language at a time."
Assert-True ($languageWindowXaml -notmatch 'Binding NativeName|Binding EnglishName') "First-run language selector mixes Arabic and English labels."
Assert-True ($localizationService -notmatch 'TranslateElement\(') "Legacy visual-tree translation remains and can re-translate already localized controls."
Assert-True ($localizationService -match 'IsTechnicalIdentifier') "Strict Arabic fallback for unknown English prose is missing."
Assert-True ($mainWindowXaml -match 'Binding="\{Binding LocationText\}"') "Install-monitor locations bypass the localization boundary."
Assert-True ($mainWindowXaml -notmatch 'EnableTemporaryMemoryReleaseCheckBox') "Removed temporary-memory option is still exposed in Settings."
Assert-True ($mainWindowXaml -notmatch '(Text|Content|Header|Title)="[^"{}]*(?:[A-Za-z]{3,}|[؀-ۿ]{3,})') "Modern XAML contains hard-coded visible language text."


$legacyLocalization = Read-Text "src\SafeWindowsCleaner.Win7\Services\LocalizationService.cs"
Assert-True ($legacyLocalization -notmatch '"(?:es|fr|it|ru|de|pt)"') "Legacy production source exposes an unsupported language."
Assert-True ($legacyLocalization -match '\{"Arabic", new\[\]\{"العربية", "Arabic"\}\}') "Legacy Arabic language label is not interface-localized."
Assert-True ($legacyLocalization -match '\{"English", new\[\]\{"الإنجليزية", "English"\}\}') "Legacy English language label is not interface-localized."
$legacyMainWindow = Read-Text "src\SafeWindowsCleaner.Win7\MainWindow.xaml.cs"
Assert-True ($legacyMainWindow -notmatch 'MessageBox\.Show\(ex\.Message') "Legacy UI exposes raw English exception text."
Assert-True ($legacyMainWindow -match 'LocalizationService\.Get\("OperationFailed"\)') "Legacy UI has no language-safe error message."
$legacyXaml = Read-Text "src\SafeWindowsCleaner.Win7\MainWindow.xaml"
Assert-True ($legacyXaml -notmatch '(Text|Content|Header|Title)="[^"{}]*(?:[A-Za-z]{3,}|[؀-ۿ]{3,})') "Legacy XAML contains hard-coded visible language text."

$virtualMemoryService = Read-Text "src\SafeWindowsCleaner\Services\VirtualMemoryService.cs"
$virtualMemoryUi = Read-Text "src\SafeWindowsCleaner\MainWindow.VirtualMemory.cs"
Assert-True ($virtualMemoryService -match 'FixedPageFileSizeMb\s*=\s*16\s*\*\s*1024') "16 GB maximum virtual-memory preset is missing."
Assert-True ($virtualMemoryService -match 'MediumPageFileSizeMb\s*=\s*8\s*\*\s*1024') "8 GB adaptive virtual-memory preset is missing."
Assert-True ($virtualMemoryService -match 'MinimumPageFileSizeMb\s*=\s*4\s*\*\s*1024') "4 GB adaptive virtual-memory preset is missing."
Assert-True ($virtualMemoryService -match 'MinimumFreeBytesAfterApply\s*=\s*8L\s*\*\s*1024L') "Protected Windows free-space reserve is missing."
Assert-True ($virtualMemoryService -match 'GetRecommendedPageFileSizeMb') "Adaptive virtual-memory sizing is missing."
Assert-True ($virtualMemoryService -match 'ManagementObjectSearcher') "Virtual-memory automatic management does not use the Windows management API directly."
Assert-True ($virtualMemoryService -match 'ManagementTimeout') "Virtual-memory WMI operations need a bounded timeout."
Assert-True ($virtualMemoryService -match 'PowerShellTimeout') "Virtual-memory compatibility fallback needs a bounded timeout."
Assert-True ($virtualMemoryService -match 'VerifyPagingFilesWritten') "Virtual-memory registry writes are not verified."
Assert-True ($virtualMemoryService -match 'VerifyAutomaticManagementAsync') "Automatic page-file management changes are not verified."
Assert-True ($virtualMemoryService -match 'Environment\.Is64BitOperatingSystem\s*\?\s*RegistryView\.Registry64\s*:\s*RegistryView\.Registry32') "Virtual-memory registry access is not compatible with both x64 and x86 Windows."
Assert-True ($virtualMemoryService -match 'virtual-memory-backup\.json') "Virtual-memory rollback backup is missing."
Assert-True ($virtualMemoryUi -match 'ApplyRecommendedAsync') "UI is not connected to adaptive virtual-memory sizing."
Assert-True ($virtualMemoryUi -match '@VirtualMemoryInsufficientSpace') "Friendly low-disk-space handling is missing."
Assert-True ($virtualMemoryUi -match '@VirtualMemoryDetailsSaved') "Virtual-memory errors still expose raw diagnostic paths."

$legacyVirtualMemory = Read-Text "src\SafeWindowsCleaner.Win7\Services\VirtualMemoryService.cs"
Assert-True ($legacyVirtualMemory -match 'MaximumSizeMb\s*=\s*16384') "Legacy 16 GB preset is missing."
Assert-True ($legacyVirtualMemory -match 'MediumSizeMb\s*=\s*8192') "Legacy 8 GB fallback is missing."
Assert-True ($legacyVirtualMemory -match 'MinimumSizeMb\s*=\s*4096') "Legacy 4 GB fallback is missing."
Assert-True ($legacyVirtualMemory -match 'MinimumFreeBytesAfterApply') "Legacy free-space protection is missing."

$automaticCleanup = Read-Text "src\SafeWindowsCleaner\MainWindow.AutomaticCleanup.cs"
foreach ($forbiddenCall in @('TrimWorkingSetsAsync(', 'EmptyWorkingSet(', 'EndSelectedAsync(', '.Kill(', 'CloseMainWindow(')) {
    Assert-True (-not $automaticCleanup.Contains($forbiddenCall)) "Automatic cleanup contains forbidden process action '$forbiddenCall'."
}
$productionSources = (Get-ChildItem (Join-Path $root "src\SafeWindowsCleaner") -Recurse -Filter *.cs | ForEach-Object { Get-Content $_.FullName -Raw }) -join "`n"
Assert-True ($productionSources -notmatch 'EmptyWorkingSet|TrimWorkingSetsAsync') "Temporary working-set trimming remains in the Lite product."

$updateService = Read-Text "src\SafeWindowsCleaner\Services\UpdateService.cs"
Assert-True ($updateService -match 'Environment\.Is64BitProcess') "Updater does not preserve the installed application architecture."
Assert-True ($updateService -match '-Win10-11-\{architecture\}-Setup\.exe') "Updater does not select the matching x64/x86 Setup package."
Assert-True ($updateService -match 'SelectSetupAssetName') "Architecture-aware update asset selector is missing."
Assert-True ($updateService -notmatch 'Windows7-8-8.1-Legacy-Setup\.exe') "Modern updater must never offer the Windows Legacy package."
$testsSource = Read-Text "tests\SafeWindowsCleaner.SafetyTests\Program.cs"
Assert-True ($testsSource -match 'Updater selects the matching Windows architecture') "Updater architecture regression test is missing."
Assert-True ($testsSource -match 'new Version\(2, 4, 0\)') "Updater regression tests do not target the current 2.4.0 release."
Assert-True ($testsSource -match 'SafeWindowsCleaner-2\.4\.0-Windows7-8-8\.1-Legacy-Setup\.exe') "Updater regression test does not use the current Windows Legacy package name."

$appSource = Read-Text "src\SafeWindowsCleaner\App.xaml.cs"
Assert-True ($appSource -match 'SafeWindowsCleanerLite\.Application') "Modern single-instance mutex is missing."
Assert-True ($appSource -match '_ = RunCommandLineModeAsync\(e\.Args\)') "Command-line mode must run asynchronously."
Assert-True ($appSource -notmatch 'CommandLineRunner\.RunAsync\([^\r\n]+\)\.GetAwaiter\(\)\.GetResult\(\)') "Command-line mode can deadlock the WPF dispatcher."

$workflow = Read-Text ".github\workflows\build-windows.yml"
foreach ($packageName in @(
    'SafeWindowsCleaner-2.4.0-Win10-11-x64',
    'SafeWindowsCleaner-2.4.0-Win10-11-x86',
    'SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy'
)) {
    Assert-True ($workflow -match [regex]::Escape($packageName)) "Workflow output '$packageName' is missing."
}
Assert-True ($workflow -match '(?ms)- name: Smoke test modern Setup packages\s+shell: pwsh\s+timeout-minutes: 15') "Modern Setup smoke test has no bounded workflow timeout."
Assert-True (($workflow | Select-String -Pattern 'WaitForExit\(180000\)' -AllMatches).Matches.Count -ge 2) "Both modern installers need bounded install and uninstall timeouts."
Assert-True ($workflow -match 'actions/checkout@v7') "Workflow checkout action is stale."
Assert-True ($workflow -match 'actions/setup-dotnet@v6') "Workflow setup-dotnet action is stale."
Assert-True ($workflow -match 'WINDOWS7-LEGACY-README-AR-EN\.txt') "Legacy package guidance is missing from the build."
Assert-True ($workflow -match 'PACKAGE-SELECTION-AR-EN\.txt') "Package-selection guidance is missing from the build."

$localBuild = Read-Text "build-windows.ps1"
foreach ($packageName in @(
    'SafeWindowsCleaner-$version-Win10-11-x64',
    'SafeWindowsCleaner-$version-Win10-11-x86',
    'SafeWindowsCleaner-$version-Windows7-8-8.1-Legacy'
)) {
    Assert-True ($localBuild -match [regex]::Escape($packageName)) "Local build script output '$packageName' is missing."
}

$obsoletePath = Join-Path $root "src\SafeWindowsCleaner\MainWindow.V17.cs"
if (Test-Path $obsoletePath) { Remove-Item $obsoletePath -Force }
Assert-True (-not (Test-Path $obsoletePath)) "Obsolete MainWindow.V17.cs could not be removed."
Assert-True ((Read-Text "src\SafeWindowsCleaner\SafeWindowsCleaner.csproj") -match '<Compile Remove="MainWindow\.V17\.cs"\s*/>') "The modern project must exclude obsolete MainWindow.V17.cs."

Write-Host "Release configuration validation passed for v$ExpectedVersion." -ForegroundColor Green
