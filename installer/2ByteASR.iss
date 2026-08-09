#ifndef MyAppVersion
  #define MyAppVersion "0.1.0-dev"
#endif

#define MyAppName "2ByteASR"
#define MyAppPublisher "2ByteASR contributors"
#define MyAppExeName "2ByteASR.exe"

[Setup]
AppId={{D2CA55A8-6992-4C39-BAF1-2D790E9B5E26}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=2ByteASR-Setup-{#MyAppVersion}
SetupIconFile=..\assets\2byteasr.ico
; 程序文件本身只有约 6 MB，但首次配置还需下载模型（默认约 7 GB，含可选 Qwen 约 11.7 GB）并创建
; Python 环境（约 4 GB），安装器按 15 GB 提示磁盘空间要求。
; （该参数按字节解析：15 GB = 16106127360）
ExtraDiskSpaceRequired=16106127360
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
#ifdef MySignTool
SignTool={#MySignTool}
SignedUninstaller=yes
#endif

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce

[Files]
#ifdef MySignTool
Source: "..\2ByteASR.exe"; DestDir: "{app}"; Flags: ignoreversion signonce
#else
Source: "..\2ByteASR.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif
Source: "..\*.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\*.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\*.json"; DestDir: "{app}"; Excludes: "secrets.json,2byteasr_settings.json,game_profiles.json"; Flags: ignoreversion
Source: "..\2byteasr_settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\game_profiles.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\*.txt"; DestDir: "{app}"; Excludes: "glossary.txt"; Flags: ignoreversion
Source: "..\glossary.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CONFIGURATION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SECRETS_SETUP.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\UPDATING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\twobyteasr\*.py"; DestDir: "{app}\twobyteasr"; Flags: ignoreversion
Source: "..\lexicons\*.json"; DestDir: "{app}\lexicons"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\scripts\*.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\2byteasr.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\2byteasr.ico"; Tasks: desktopicon

[Run]
; 环境变量 2BYTEASR_NO_PAUSE=1：安装器触发的配置成功后不等待按键（失败仍会暂停显示错误）
Filename: "{cmd}"; Parameters: "/c ""set 2BYTEASR_NO_PAUSE=1&& ""{app}\setup_2byteasr.bat"""; Description: "配置/更新环境并校验模型（已有模型不会重复下载）"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv-main"
Type: filesandordirs; Name: "{app}\.venv-moss"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\third_party"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\twobyteasr\__pycache__"
