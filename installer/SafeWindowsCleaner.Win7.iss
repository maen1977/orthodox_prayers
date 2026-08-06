#define MyAppName "Safe Windows Cleaner Lite - Windows Legacy"
#define MyAppVersion "2.4.0"
#define MyAppPublisher "معن حنونة للستلايت"
#define MyAppExeName "SafeWindowsCleaner.exe"
#define MyPackageName "SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy"

[Setup]
AppId={{CE435A11-66CC-4B7E-A669-F45DCE612BB4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}
DefaultDirName={autopf}\Safe Windows Cleaner Lite
DefaultGroupName=Safe Windows Cleaner Lite
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename={#MyPackageName}-Setup
SetupIconFile=..\src\SafeWindowsCleaner.Win7\Assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/normal
SolidCompression=no
WizardStyle=modern
ArchitecturesAllowed=x86compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupMutex=SafeWindowsCleanerLite.Setup
UninstallDisplayName={#MyAppName}
Uninstallable=yes
MinVersion=6.1sp1
OnlyBelowVersion=10.0
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter={#MyAppExeName}
UsePreviousAppDir=yes
UsePreviousTasks=yes
VersionInfoVersion=2.4.0.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription=Windows 7 SP1, Windows 8, and Windows 8.1 compatible lightweight cleaner
VersionInfoCompany={#MyAppPublisher}
SetupLogging=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ar"; MessagesFile: "compiler:Default.isl,Languages\Arabic.isl"

[Messages]
en.WindowsVersionNotSupported=This Legacy package runs on Windows 7 SP1, Windows 8, and Windows 8.1. Use the Windows 10/11 x64 or x86 package on newer systems.
ar.WindowsVersionNotSupported=تعمل حزمة Legacy هذه على ويندوز 7 SP1 وويندوز 8 وويندوز 8.1. استخدم حزمة ويندوز 10 أو 11 المناسبة على الأنظمة الأحدث.

[CustomMessages]
en.CreateDesktopShortcut=Create a desktop shortcut
ar.CreateDesktopShortcut=إنشاء اختصار على سطح المكتب
en.AdditionalShortcuts=Additional shortcuts:
ar.AdditionalShortcuts=اختصارات إضافية:
en.LaunchProgram=Launch Safe Windows Cleaner Lite
ar.LaunchProgram=تشغيل منظف ويندوز الآمن لايت
en.DotNetMissing=.NET Framework 4.6.1 or later is required. Install it, restart Windows, then run Setup again.
ar.DotNetMissing=يلزم تثبيت ‎.NET Framework 4.6.1 أو أحدث، ثم إعادة تشغيل ويندوز وتشغيل المثبت مرة أخرى.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopShortcut}"; GroupDescription: "{cm:AdditionalShortcuts}"; Flags: checkedonce

[InstallDelete]
Type: filesandordirs; Name: "{app}\*"; Check: IsSafeApplicationDirectory

[Files]
Source: "..\publish\win7\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\SafeWindowsCleaner"; ValueType: string; ValueName: "LanguageCode"; ValueData: "{language}"; Flags: uninsdeletekey

[Icons]
Name: "{autoprograms}\Safe Windows Cleaner Lite - Windows Legacy"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Safe Windows Cleaner Lite"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName} /T >nul 2>&1"; Flags: runhidden waituntilterminated; RunOnceId: "StopSafeWindowsCleanerWin7"
Filename: "{app}\{#MyAppExeName}"; Parameters: "--restore-virtual-memory"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "RestoreVirtualMemoryWin7"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*"
Type: filesandordirs; Name: "{localappdata}\SafeWindowsCleaner"
Type: filesandordirs; Name: "{userappdata}\SafeWindowsCleaner"
Type: filesandordirs; Name: "{commonappdata}\SafeWindowsCleaner"
Type: dirifempty; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--language={language}"; Description: "{cm:LaunchProgram}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
const
  Net461MinimumRelease = 394254;

function IsDotNet461OrLaterInstalled(): Boolean;
var
  Release: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM64,
    'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full',
    'Release', Release) and (Release >= Net461MinimumRelease);
  if not Result then
    Result := RegQueryDWordValue(HKLM32,
      'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full',
      'Release', Release) and (Release >= Net461MinimumRelease);
end;

function IsSafeApplicationDirectory(): Boolean;
var
  AppDirectory: String;
begin
  AppDirectory := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  Result :=
    (CompareText(ExtractFileName(AppDirectory), 'Safe Windows Cleaner Lite') = 0) or
    FileExists(AddBackslash(AppDirectory) + '{#MyAppExeName}');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  Exec(ExpandConstant('{cmd}'),
       '/C taskkill /F /IM {#MyAppExeName} /T >nul 2>&1',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(400);
end;

function InitializeSetup(): Boolean;
begin
  Result := IsDotNet461OrLaterInstalled();
  if not Result then
    MsgBox(ExpandConstant('{cm:DotNetMissing}'), mbError, MB_OK);
end;
