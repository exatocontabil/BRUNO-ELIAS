; Instalador do Exato Web (Inno Setup 6). Gerado pelo montar_instalador.py (define Versao, Origem e Saida).
; Instala para o usuário do Windows (sem pedir administrador), leva o seu próprio Python e as peças que o Exato precisa:
; quem instala não precisa instalar nada além deste programa.
#ifndef Versao
  #define Versao "0.0"
#endif
#ifndef Origem
  #define Origem "stage"
#endif
#ifndef Saida
  #define Saida "dist"
#endif

[Setup]
AppId={{6E2B6C0A-47C3-4F58-9D0B-5E8A1C7D2F31}
AppName=Exato Web
AppVersion={#Versao}
AppVerName=Exato Web {#Versao}
AppPublisher=Exato Soluções Contábeis
DefaultDirName={localappdata}\Programs\Exato Web
DefaultGroupName=Exato Web
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Saida}
OutputBaseFilename=Exato_Web_Instalador_{#Versao}
SetupIconFile={#Origem}\exato.ico
UninstallDisplayIcon={app}\exato.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
RestartApplications=no
UsePreviousAppDir=yes
VersionInfoVersion=1.0.0.0
VersionInfoCompany=Exato Soluções Contábeis
VersionInfoDescription=Instalador do Exato Web

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
WelcomeLabel1=Bem-vindo ao Exato Web
WelcomeLabel2=Este programa instala o Exato Web neste computador.%n%nEle busca e guarda as notas fiscais dos seus clientes, faz a auditoria e envia o que precisa para a Domínio.%n%nNão é preciso instalar mais nada: tudo o que o Exato usa já vai junto.

[Tasks]
Name: "iniciar_com_windows"; Description: "Ligar o Exato sozinho quando o Windows iniciar"; GroupDescription: "Opções:"
Name: "atalho_area"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Opções:"

[Files]
Source: "{#Origem}\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Origem}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Origem}\exato.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Exato Web"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\abrir.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\exato.ico"
Name: "{group}\Parar o Exato"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\parar.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\exato.ico"
Name: "{group}\Desinstalar o Exato Web"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Exato Web"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\abrir.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\exato.ico"; Tasks: atalho_area

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ExatoWeb"; ValueData: """{app}\python\pythonw.exe"" ""{app}\app\iniciar.pyw"""; Tasks: iniciar_com_windows; Flags: uninsdeletevalue

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\iniciar.pyw"""; WorkingDir: "{app}\app"; Flags: nowait runhidden
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\abrir.pyw"""; WorkingDir: "{app}\app"; Description: "Abrir o Exato agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\parar.pyw"" /silencioso"; WorkingDir: "{app}\app"; Flags: runhidden waituntilterminated; RunOnceId: "PararExato"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"

[Code]
var
  PaginaDados: TInputDirWizardPage;

function ParametroDados(): String;
var
  i: Integer;
  p: String;
begin
  Result := '';
  for i := 1 to ParamCount do
  begin
    p := ParamStr(i);
    if Pos('/DADOS=', Uppercase(p)) = 1 then
      Result := RemoveQuotes(Copy(p, 8, MaxInt));
  end;
end;

procedure InitializeWizard;
var
  padrao: String;
begin
  padrao := ExpandConstant('{localappdata}\Exato Web\Dados');
  if DirExists(ExpandConstant('{%USERPROFILE}\ExatoWebDados')) then
    padrao := ExpandConstant('{%USERPROFILE}\ExatoWebDados');
  PaginaDados := CreateInputDirPage(wpSelectDir, 'Onde guardar os dados',
    'Escolha a pasta onde o Exato vai guardar as empresas, as notas e os certificados.',
    'Escolha um disco com bastante espaço livre (as notas ocupam bastante com o tempo). Esta pasta fica só neste computador. Depois de instalar, configure uma cópia de segurança em outro disco.',
    False, '');
  PaginaDados.Add('');
  PaginaDados.Values[0] := GetPreviousData('Dados', padrao);
  if ParametroDados() <> '' then
    PaginaDados.Values[0] := ParametroDados();
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'Dados', PaginaDados.Values[0]);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  pasta, raiz: String;
  livre, total: Cardinal;
begin
  Result := True;
  if CurPageID = PaginaDados.ID then
  begin
    pasta := Trim(PaginaDados.Values[0]);
    if (Length(pasta) < 4) or (Copy(pasta, 2, 1) <> ':') then
    begin
      MsgBox('Escolha uma pasta deste computador (por exemplo C:\ExatoDados ou D:\ExatoDados).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    raiz := Copy(pasta, 1, 3);
    if GetSpaceOnDisk(raiz, True, livre, total) then
      if livre < 1500 then
        if MsgBox('O disco ' + raiz + ' tem pouco espaço livre (' + IntToStr(livre) + ' MB). O Exato pode ficar sem espaço para guardar as notas. Quer escolher outra pasta?', mbConfirmation, MB_YESNO) = IDYES then
        begin
          Result := False;
          Exit;
        end;
    if not ForceDirectories(pasta) then
    begin
      MsgBox('Não foi possível criar essa pasta. Escolha outra.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure PararSeInstalado();
var
  pythonw, parar: String;
  codigo: Integer;
begin
  pythonw := ExpandConstant('{app}\python\pythonw.exe');
  parar := ExpandConstant('{app}\app\parar.pyw');
  if FileExists(pythonw) and FileExists(parar) then
    Exec(pythonw, '"' + parar + '" /silencioso', '', SW_HIDE, ewWaitUntilTerminated, codigo);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  PararSeInstalado();
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\app\dados.txt'), Trim(PaginaDados.Values[0]) + #13#10, False);
end;
