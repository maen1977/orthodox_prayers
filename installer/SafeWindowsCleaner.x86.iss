#define MyAppName "Safe Windows Cleaner Lite"
#define MyAppVersion "2.4.0"
#define MyAppPublisher "معن حنونة للستلايت"
#define MyAppPhone "00962788272988"
#define MyAppExeName "SafeWindowsCleaner.exe"
#define MyPackageName "SafeWindowsCleaner-2.4.0-Win10-11-x86"

[Setup]
AppId={{CE435A11-66CC-4B7E-A669-F45DCE612BB4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} (Windows 10/11 x86)
AppPublisher={#MyAppPublisher}
AppSupportPhone={#MyAppPhone}
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}
AppComments=Publisher: {#MyAppPublisher} | Phone: {#MyAppPhone} | Package: x86
DefaultDirName={autopf}\Safe Windows Cleaner Lite
DefaultGroupName=Safe Windows Cleaner Lite
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename={#MyPackageName}-Setup
SetupIconFile=..\src\SafeWindowsCleaner\Assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/normal
SolidCompression=no
WizardStyle=modern
ArchitecturesAllowed=x86compatible
; On 64-bit Windows this keeps the same install directory and uninstall registry
; view as the x64 package, while the x86 application itself still runs normally.
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupMutex=SafeWindowsCleanerLite.Setup
UninstallDisplayName={#MyAppName}
Uninstallable=yes
UninstallRestartComputer=no
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter={#MyAppExeName}
UsePreviousAppDir=yes
UsePreviousTasks=yes
VersionInfoVersion=2.4.0.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription=Windows 10/11 x86 self-contained Lite installer
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
SetupLogging=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ar"; MessagesFile: "compiler:Default.isl,Languages\Arabic.isl"

[Messages]
en.WindowsVersionNotSupported=This package requires Windows 10 or Windows 11. Use the Legacy package on Windows 7 SP1, Windows 8, or Windows 8.1.
ar.WindowsVersionNotSupported=تتطلب هذه الحزمة ويندوز 10 أو 11. استخدم حزمة Legacy على ويندوز 7 SP1 أو ويندوز 8 أو ويندوز 8.1.

[CustomMessages]
en.CreateDesktopShortcut=Create a desktop shortcut
ar.CreateDesktopShortcut=إنشاء اختصار على سطح المكتب
en.AdditionalShortcuts=Additional shortcuts:
ar.AdditionalShortcuts=اختصارات إضافية:
en.LaunchProgram=Launch Safe Windows Cleaner Lite
ar.LaunchProgram=تشغيل منظف ويندوز الآمن لايت

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopShortcut}"; GroupDescription: "{cm:AdditionalShortcuts}"; Flags: checkedonce

[InstallDelete]
Type: filesandordirs; Name: "{app}\*"; Check: IsSafeApplicationDirectory

[Files]
Source: "..\publish\win-x86\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\SafeWindowsCleaner"; ValueType: string; ValueName: "LanguageCode"; ValueData: "{language}"; Flags: uninsdeletekey

[Icons]
Name: "{autoprograms}\Safe Windows Cleaner Lite"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Safe Windows Cleaner Lite"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName} /T >nul 2>&1"; Flags: runhidden waituntilterminated; RunOnceId: "StopSafeWindowsCleaner"
Filename: "{app}\{#MyAppExeName}"; Parameters: "--restore-virtual-memory"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "RestoreVirtualMemory"
Filename: "{cmd}"; Parameters: "/C schtasks /Delete /TN ""SafeWindowsCleaner Lite Weekly Cleanup"" /F >nul 2>&1"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveScheduledCleanup"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*"
Type: filesandordirs; Name: "{localappdata}\SafeWindowsCleaner"
Type: filesandordirs; Name: "{userappdata}\SafeWindowsCleaner"
Type: filesandordirs; Name: "{commonappdata}\SafeWindowsCleaner"
Type: dirifempty; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--language={language}"; Description: "{cm:LaunchProgram}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runascurrentuser
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Flags: nowait; Check: ShouldRestartAfterSilentUpdate

[Code]
function HasCommandLineParameter(const Expected: String): Boolean;
var
  Index: Integer;
begin
  Result := False;
  for Index := 1 to ParamCount do
  begin
    if CompareText(ParamStr(Index), Expected) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
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
  Sleep(500);
end;

function ShouldRestartAfterSilentUpdate(): Boolean;
begin
  Result := WizardSilent and HasCommandLineParameter('/RESTARTAPP=1');
end;
