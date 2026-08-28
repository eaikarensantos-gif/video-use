; Inno Setup script for video-use. Compiled by the GitHub Actions Windows
; build (.github/workflows/build-windows-installer.yml) against the
; PyInstaller onedir output in dist\video-use\.
;
; Installs per-user (no admin prompt, no UAC) under
; %LOCALAPPDATA%\Programs\video-use — matches how most modern per-user
; Windows apps (VS Code, Discord, etc.) install themselves.

#ifndef MyAppVersion
  #define MyAppVersion "0.5.0"
#endif

[Setup]
AppId={{B3B6E6C1-9A3E-4C7C-9C7E-VIDEOUSE0001}
AppName=video-use
AppVersion={#MyAppVersion}
AppPublisher=video-use
AppPublisherURL=https://github.com/eaikarensantos-gif/video-use
AppUpdatesURL=https://github.com/eaikarensantos-gif/video-use/releases
DefaultDirName={localappdata}\Programs\video-use
DefaultGroupName=video-use
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist-installer
OutputBaseFilename=video-use-setup
SetupIconFile=..\..\Video-Use.ico
UninstallDisplayIcon={app}\video-use.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\video-use\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\video-use"; Filename: "{app}\video-use.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall video-use"; Filename: "{uninstallexe}"
Name: "{userdesktop}\video-use"; Filename: "{app}\video-use.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\video-use.exe"; Description: "Launch video-use now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\video-use-crash.log"
