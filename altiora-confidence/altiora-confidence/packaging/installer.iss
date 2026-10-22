; Inno Setup recipe: turns dist\Altiora Confidence into Setup_Altiora_Confidence_<version>.exe
; Installs for the current user only -> no administrator rights needed.

#define AppName "Altiora Confidence"
#ifndef AppVersion
  #define AppVersion "1.0"
#endif
#define AppExe "Altiora Confidence.exe"

[Setup]
AppId={{6C1F4E2A-8B7D-4F43-9A51-3E0D2C7B9A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\output
OutputBaseFilename=Setup_Altiora_Confidence_{#AppVersion}
SetupIconFile=..\app\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.RightClick=Ajouter « Anonymiser » au clic droit sur les PDF
en.RightClick=Add "Anonymise" to the right-click menu of PDFs
fr.MenuText=Anonymiser avec Altiora Confidence
en.MenuText=Anonymise with Altiora Confidence

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "rightclick"; Description: "{cm:RightClick}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\AltioraConfidence"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuText}"; Flags: uninsdeletekey; Tasks: rightclick
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\AltioraConfidence"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"""; Tasks: rightclick
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\AltioraConfidence\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: rightclick

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
