# Cria atalhos do Exato Web na Area de Trabalho, com tecla de atalho:
#   Ctrl+Alt+A = Atualizar o site | Ctrl+Alt+P = Parar o site | Ctrl+Alt+L = Ligar o site | e um atalho "Exato Web" que abre o site.
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
try {
    $pasta = (Split-Path -Parent $MyInvocation.MyCommand.Path).TrimEnd('\')
    if ($pasta.StartsWith('\\')) { throw 'Rode a partir da pasta do site neste computador (ex.: C:\ExatoWeb).' }
    $desk = [Environment]::GetFolderPath('Desktop'); $sh = New-Object -ComObject WScript.Shell
    function Atalho($nome, $alvo, $tecla, $desc) {
        $l = $sh.CreateShortcut((Join-Path $desk ($nome + '.lnk'))); $l.TargetPath = $alvo; $l.WorkingDirectory = $pasta; $l.Description = $desc; if ($tecla) { $l.Hotkey = $tecla }
        $l.IconLocation = "$env:SystemRoot\System32\shell32.dll,238"; $l.Save()
    }
    Atalho 'Exato Web - Atualizar' (Join-Path $pasta 'ATUALIZAR_SITE.bat') 'CTRL+ALT+A' 'Atualiza o Exato Web com o pacote novo'
    Atalho 'Exato Web - Parar' (Join-Path $pasta 'PARAR_SITE.bat') 'CTRL+ALT+P' 'Desliga o Exato Web'
    Atalho 'Exato Web - Ligar' (Join-Path $pasta 'LIGAR_SITE.bat') 'CTRL+ALT+L' 'Liga o Exato Web'
    $url = 'http://127.0.0.1:8443'; $arq = Join-Path $pasta 'para_os_outros_pcs\endereco.txt'
    if (Test-Path $arq) { $url = 'https://' + (Get-Content $arq | Select-Object -First 1).Trim() }
    $u = $sh.CreateShortcut((Join-Path $desk 'Exato Web.url')); $u.TargetPath = $url; $u.Save()
    Write-Host 'Atalhos criados na Area de Trabalho:' -ForegroundColor Green
    Write-Host '  Exato Web            - abre o site'
    Write-Host '  Exato Web - Atualizar  (Ctrl+Alt+A)'
    Write-Host '  Exato Web - Parar      (Ctrl+Alt+P)'
    Write-Host '  Exato Web - Ligar      (Ctrl+Alt+L)'
    Write-Host 'As teclas de atalho valem enquanto os atalhos ficarem na Area de Trabalho. Para mudar a tecla: botao direito no atalho > Propriedades > Tecla de atalho.'
} catch { Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red }
Pausa
