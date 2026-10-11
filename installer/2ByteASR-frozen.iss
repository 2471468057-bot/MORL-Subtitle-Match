; Build only from the verified, clean frozen payload. No source checkout glob.
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#ifndef MyAppVersion
  #error MyAppVersion is required
#endif

[Setup]
AppId={code:ApplicationId}
#ifdef QAInstall
AppName=2ByteASR QA
DefaultDirName={localappdata}\Programs\2ByteASR-QA-20260927
OutputBaseFilename=2ByteASR-QA-Setup-{#MyAppVersion}
CloseApplications=no
UsePreviousAppDir=no
#else
AppName=2ByteASR
DefaultDirName={localappdata}\Programs\2ByteASR
OutputBaseFilename=2ByteASR-Setup-{#MyAppVersion}
CloseApplications=yes
#endif
UsePreviousLanguage=no
AppVersion={#MyAppVersion}
#ifdef MyAppNumericVersion
VersionInfoVersion={#MyAppNumericVersion}
#endif
VersionInfoProductName=2ByteASR
VersionInfoDescription=2ByteASR (兔白字幕) Setup
MinVersion=10.0.19045
DisableDirPage=no
AppPublisher=2ByteASR contributors
DefaultGroupName=2ByteASR
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
RestartApplications=no
OutputDir={#ReleaseDir}
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\2ByteASR.exe
LicenseFile={#PayloadDir}\LICENSE
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
AllowNoIcons=yes
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce
Name: "projectassociation"; Description: "关联兔白字幕工程（.2byteproj）"; GroupDescription: "工程文件："; Flags: checkedonce; Check: NotAudit

[Registry]
Root: HKCU; Subkey: "Software\Classes\2ByteASR.Project"; ValueType: string; ValueName: ""; ValueData: "兔白字幕工程"; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\2ByteASR.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\2ByteASR.exe"",0"; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\2ByteASR.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\2ByteASR.exe"" ""%1"""; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\.2byteproj"; ValueType: string; ValueName: ""; ValueData: "2ByteASR.Project"; Flags: createvalueifdoesntexist; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\.2byteproj\OpenWithProgids"; ValueType: string; ValueName: "2ByteASR.Project"; ValueData: ""; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\Applications\2ByteASR.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\2ByteASR.exe"" ""%1"""; Tasks: projectassociation; Check: NotAudit
Root: HKCU; Subkey: "Software\Classes\Applications\2ByteASR.exe\SupportedTypes"; ValueType: string; ValueName: ".2byteproj"; ValueData: ""; Tasks: projectassociation; Check: NotAudit

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Excludes: "2byteasr_settings.json,game_profiles.json,glossary.txt"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\2byteasr_settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#PayloadDir}\game_profiles.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#PayloadDir}\glossary.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
; AUDIT installs never touch the real Start menu or desktop. With
; /AUDITSHORTCUTS=<folder> they write the same shortcut into that folder so
; QA can check its target, working folder and icon after an upgrade.
Name: "{code:AuditShortcutDir}\2ByteASR"; Filename: "{app}\2ByteASR.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\app_icon.ico"; AppUserModelID: "2ByteASR.Desktop.2026"; Check: IsAuditShortcut
Name: "{group}\2ByteASR"; Filename: "{app}\2ByteASR.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\app_icon.ico"; AppUserModelID: "2ByteASR.Desktop.2026"; Check: NotAudit
Name: "{autodesktop}\2ByteASR"; Filename: "{app}\2ByteASR.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\app_icon.ico"; AppUserModelID: "2ByteASR.Desktop.2026"; Tasks: desktopicon; Check: NotAudit

[Run]
Filename: "{app}\2ByteASR.exe"; Description: "启动 2ByteASR"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent; Check: NotAudit

[UninstallRun]
; Program files added later by the in-app component updater are not in Inno's
; uninstall log. The helper removes only files listed in 2byteasr_components.json
; (exact size match), plus its own .update-state/.update-backup folders.
Filename: "{app}\2ByteASRUpdater.exe"; Parameters: "--remove-listed ""{app}"""; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "RemoveListedProgramFiles"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.update-state"
Type: filesandordirs; Name: "{app}\.update-backup"

; Inno removes only files it installed. Models, projects and per-user settings
; created later are intentionally retained; never recursively delete {app}.
[Code]
function NotAudit: Boolean;
begin
#ifdef QAInstall
  Result := False;
#else
  Result := ExpandConstant('{param:AUDIT|0}') <> '1';
#endif
end;

function AuditShortcutDir(Param: String): String;
begin
  Result := ExpandConstant('{param:AUDITSHORTCUTS|}');
end;

function IsAuditShortcut: Boolean;
begin
  Result := (not NotAudit) and (AuditShortcutDir('') <> '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StateDir, Previous, Helper: String;
  ResultCode: Integer;
begin
  StateDir := ExpandConstant('{app}\.update-state');
  Previous := StateDir + '\previous-components.json';
  if CurStep = ssInstall then begin
    { Setup is the full, authoritative program package: an unfinished in-app
      update journal or its backups must not be replayed over these files. }
    DeleteFile(StateDir + '\journal.txt');
    DelTree(ExpandConstant('{app}\.update-backup'), True, True, True);
    if FileExists(ExpandConstant('{app}\2byteasr_components.json')) then begin
      ForceDirectories(StateDir);
      FileCopy(ExpandConstant('{app}\2byteasr_components.json'), Previous, False);
    end;
  end;
  if CurStep = ssPostInstall then begin
    { Remove program files the previous version listed and this one no longer
      ships (exact size and SHA-256 match only). Nothing else is deleted. }
    Helper := ExpandConstant('{app}\2ByteASRUpdater.exe');
    if FileExists(Previous) and FileExists(Helper) then
      Exec(Helper, '--prune "' + ExpandConstant('{app}') + '" "' + Previous + '"', '', SW_HIDE,
        ewWaitUntilTerminated, ResultCode);
  end;
end;

function ApplicationId(Param: String): String;
begin
#ifdef QAInstall
  Result := '{D2CA55A8-6992-4C39-BAF1-2D790E9B5E26}-ModelQA20260927';
#else
  if NotAudit then
    Result := '{D2CA55A8-6992-4C39-BAF1-2D790E9B5E26}'
  else
    Result := '{D2CA55A8-6992-4C39-BAF1-2D790E9B5E26}-IsolatedAudit';
#endif
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command, ExtensionDefault: String;
begin
  if (CurUninstallStep = usPostUninstall) and NotAudit then begin
    { A later repair/installation may now own the ProgID. Only remove our
      registration if its exact command still points to this installation. }
    if RegQueryStringValue(HKCU, 'Software\Classes\2ByteASR.Project\shell\open\command', '', Command)
       and (CompareText(Command, '"' + ExpandConstant('{app}\2ByteASR.exe') + '" "%1"') = 0) then begin
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\2ByteASR.Project');
      RegDeleteValue(HKCU, 'Software\Classes\.2byteproj\OpenWithProgids', '2ByteASR.Project');
      if RegQueryStringValue(HKCU, 'Software\Classes\.2byteproj', '', ExtensionDefault)
         and (ExtensionDefault = '2ByteASR.Project') then
        RegDeleteValue(HKCU, 'Software\Classes\.2byteproj', '');
    end;
    if RegQueryStringValue(HKCU, 'Software\Classes\Applications\2ByteASR.exe\shell\open\command', '', Command)
       and (CompareText(Command, '"' + ExpandConstant('{app}\2ByteASR.exe') + '" "%1"') = 0) then
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\Applications\2ByteASR.exe');
  end;
end;
