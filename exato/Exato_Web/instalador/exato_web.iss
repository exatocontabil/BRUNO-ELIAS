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
Source: "{#Origem}\caddy\*"; DestDir: "{app}\caddy"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist
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
Type: filesandordirs; Name: "{app}\caddy"

[Code]
var
  PaginaDados: TInputDirWizardPage;
  PaginaEndereco: TInputQueryWizardPage;

function ParametroEndereco(): String;
var
  i: Integer;
  p: String;
begin
  Result := '';
  for i := 1 to ParamCount do
  begin
    p := ParamStr(i);
    if Pos('/ENDERECO=', Uppercase(p)) = 1 then
      Result := RemoveQuotes(Copy(p, 11, MaxInt));
  end;
end;

{ Procura o nome do endereço com cadeado já usado neste computador (instalação antiga). }
function NomeNoArquivo(arq: String): String;
var
  linhas: TArrayOfString;
  i: Integer;
  t: String;
begin
  Result := '';
  if not FileExists(arq) then Exit;
  if not LoadStringsFromFile(arq, linhas) then Exit;
  for i := 0 to GetArrayLength(linhas) - 1 do
  begin
    t := Trim(linhas[i]);
    if (Length(t) > 3) and (Copy(t, Length(t), 1) = '{') and (Pos('.', t) > 0) and (Copy(t, 1, 1) <> '{') and (Copy(t, 1, 1) <> '#') then
    begin
      Result := Trim(Copy(t, 1, Length(t) - 1));
      Exit;
    end;
  end;
end;

function EnderecoJaUsado(): String;
begin
  Result := NomeNoArquivo('C:\ExatoWeb\caddy\Caddyfile');
  if Result = '' then Result := NomeNoArquivo(ExpandConstant('{%USERPROFILE}\ExatoWeb\caddy\Caddyfile'));
  if Result = '' then Result := NomeNoArquivo(ExpandConstant('{%USERPROFILE}\Desktop\ExatoWeb\caddy\Caddyfile'));
end;

function SoONome(t: String): String;
begin
  t := Trim(t);
  if Pos('HTTPS://', Uppercase(t)) = 1 then Delete(t, 1, 8);
  if Pos('HTTP://', Uppercase(t)) = 1 then Delete(t, 1, 7);
  while (Length(t) > 0) and (Copy(t, Length(t), 1) = '/') do Delete(t, Length(t), 1);
  Result := t;
end;

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
  PaginaEndereco := CreateInputQueryPage(PaginaDados.ID, 'Endereço do escritório',
    'Se o escritório quer abrir o Exato por um endereço seguro (com cadeado), informe-o aqui.',
    'Exemplo: fiscal.seuescritorio.com.br. O Exato prepara o endereço sozinho; o Windows pode pedir permissão de administrador uma vez. Se não quiser um endereço assim, deixe em branco: o Exato abre direto neste computador.');
  PaginaEndereco.Add('Endereço:', False);
  PaginaEndereco.Values[0] := GetPreviousData('Endereco', EnderecoJaUsado());
  if ParametroEndereco() <> '' then
    PaginaEndereco.Values[0] := ParametroEndereco();
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'Dados', PaginaDados.Values[0]);
  SetPreviousData(PreviousDataKey, 'Endereco', SoONome(PaginaEndereco.Values[0]));
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
    if (not DirExists(pasta)) and GetSpaceOnDisk(raiz, True, livre, total) then          { aviso de pouco espaco so na instalacao nova; atualizar nao precisa }
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
  pythonw, parar, pasta, dll: String;
  codigo, i: Integer;
begin
  pythonw := ExpandConstant('{app}\python\pythonw.exe');
  parar := ExpandConstant('{app}\app\parar.pyw');
  if FileExists(pythonw) and FileExists(parar) then
    Exec(pythonw, '"' + parar + '" /silencioso', '', SW_HIDE, ewWaitUntilTerminated, codigo);
  { Garantia: desliga QUALQUER processo que rode de dentro da pasta do Exato (o que ficou de fora da lista do desligamento normal). }
  pasta := ExpandConstant('{app}') + '\';
  if DirExists(pasta + 'python') then
  begin
    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith(''' + pasta + ''', [StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue"',
      '', SW_HIDE, ewWaitUntilTerminated, codigo);
    { Espera (ate 20 s) o Windows soltar os arquivos do Python. }
    dll := pasta + 'python\python3.dll';
    for i := 1 to 20 do
    begin
      if (not FileExists(dll)) or RenameFile(dll, dll + '.t') then
      begin
        if FileExists(dll + '.t') then RenameFile(dll + '.t', dll);
        Break;
      end;
      Sleep(1000);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  PararSeInstalado();
  Result := '';
end;

{ Prepara o endereco seguro (com cadeado) uma vez, com permissao de administrador. Nao repete se ja esta pronto para o mesmo endereco; instalacao antiga fica como esta. }
procedure ConfigurarEndereco(nome, dados: String);
var
  marca: String;
  linhas: TArrayOfString;
  i, codigo: Integer;
begin
  if nome = '' then Exit;
  marca := dados + '\caddy\configurado.json';
  if FileExists(marca) then
    if LoadStringsFromFile(marca, linhas) then
      for i := 0 to GetArrayLength(linhas) - 1 do
        if Pos('"nome": "' + nome + '"', linhas[i]) > 0 then Exit;
  if FileExists('C:\ExatoWeb\caddy\caddy.exe') or FileExists(ExpandConstant('{%USERPROFILE}\ExatoWeb\caddy\caddy.exe')) then
  begin
    ForceDirectories(dados + '\caddy');
    SaveStringToFile(marca, '{"nome": "' + nome + '", "modo": "legado", "versao": 1}', False);
    Exit;
  end;
  if not FileExists(ExpandConstant('{app}\caddy\caddy.exe')) then Exit;
  ShellExec('runas', ExpandConstant('{app}\python\pythonw.exe'),
    '"' + ExpandConstant('{app}\app\endereco.pyw') + '" "' + ExpandConstant('{app}') + '" "' + dados + '" "' + nome + '"',
    '', SW_HIDE, ewWaitUntilTerminated, codigo);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveStringToFile(ExpandConstant('{app}\app\dados.txt'), Trim(PaginaDados.Values[0]) + #13#10, False);
    if SoONome(PaginaEndereco.Values[0]) <> '' then
      SaveStringToFile(ExpandConstant('{app}\app\endereco.txt'), 'https://' + SoONome(PaginaEndereco.Values[0]) + #13#10, False)
    else
      DeleteFile(ExpandConstant('{app}\app\endereco.txt'));
    ConfigurarEndereco(SoONome(PaginaEndereco.Values[0]), Trim(PaginaDados.Values[0]));
  end;
end;
