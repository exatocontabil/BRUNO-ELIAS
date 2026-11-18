# Instala o Exato Web para ligar sozinho com o Windows, sem janela preta (tarefa agendada "Exato Web").
# Rode pelo INSTALAR_INICIO_AUTOMATICO.bat (ele pede permissao de administrador).
$ErrorActionPreference = 'Stop'
$Nome = 'Exato Web'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
try {
    $pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
    Write-Host '=== Exato Web: iniciar sozinho com o Windows ===' -ForegroundColor Cyan

    # 1) O site precisa estar numa pasta DESTE computador (o Windows nao liga programas direto de uma pasta de rede).
    if ($pasta.StartsWith('\\')) {
        Write-Host "A pasta do site esta na rede ($pasta)." -ForegroundColor Yellow
        $dest = Read-Host 'Para qual pasta DESTE computador copio o site? (Enter = C:\ExatoWeb)'
        if (-not $dest) { $dest = 'C:\ExatoWeb' }
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        robocopy $pasta $dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "Nao consegui copiar o site para $dest." }
        $pasta = $dest; Write-Host "Site copiado para $pasta" -ForegroundColor Green
    }
    if (-not (Test-Path (Join-Path $pasta 'web\servico.py'))) { throw 'Nao encontrei web\servico.py nesta pasta. Use o pacote mais novo do Exato Web.' }

    # 2) Python (o mesmo que o INICIAR_SERVIDOR.bat usa).
    $py = $null
    if (Get-Command py -ErrorAction SilentlyContinue) { $py = (& py -3 -c 'import sys;print(sys.executable)').Trim() }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = (& python -c 'import sys;print(sys.executable)').Trim() }
    if (-not $py) { throw 'Python nao encontrado. Instale o Python 3 e rode INSTALAR_DEPENDENCIAS.bat.' }
    $pyw = Join-Path (Split-Path $py) 'pythonw.exe'
    if (-not (Test-Path $pyw)) { throw "Nao achei o pythonw.exe ao lado de $py." }
    & $py -c 'import uvicorn, fastapi' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Faltam as dependencias do site. Rode INSTALAR_DEPENDENCIAS.bat e tente de novo.' }

    # 3) Usuario do Windows que vai rodar o site. TEM de ser o mesmo que usou o site ate agora (o cofre dos certificados e os dados ficam ligados a ele).
    $padrao = "$env:USERDOMAIN\$env:USERNAME"
    Write-Host ''
    Write-Host 'Importante: use o MESMO usuario do Windows que ja usava o site (os certificados guardados e os dados pertencem a ele).' -ForegroundColor Yellow
    $usuario = Read-Host "Usuario do Windows (Enter = $padrao)"
    if (-not $usuario) { $usuario = $padrao }
    $senha = Read-Host "Senha do Windows de $usuario (so o Windows guarda). Se este usuario NAO tem senha, so aperte Enter" -AsSecureString
    $plana = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($senha))
    $semSenha = -not $plana
    if ($semSenha) {
        Write-Host ''
        Write-Host 'Sem senha, o Windows nao deixa ligar o site antes de alguem entrar. Entao ele vai ligar assim que ESTE USUARIO entrar no Windows (tambem escondido, sem janela preta).' -ForegroundColor Yellow
        Write-Host 'Dica: para ligar mesmo com o computador reiniciado e ninguem presente, ative a entrada automatica no Windows (digite netplwiz no menu Iniciar) ou crie uma senha.' -ForegroundColor Yellow
    }

    # 4) Se o site antigo (janela preta) esta aberto, avisa.
    $porta = 8443
    $uso = New-Object Net.Sockets.TcpClient
    try { $uso.Connect('127.0.0.1', $porta); $uso.Close(); throw "O site ja esta ligado (porta $porta). Feche a janela preta do site (Ctrl+C) e rode este instalador de novo." } catch [System.Net.Sockets.SocketException] { }

    # 5) Cria a tarefa: liga com o Windows, roda escondida, reinicia sozinha se cair, sem limite de tempo.
    $acao = New-ScheduledTaskAction -Execute $pyw -Argument '-m web.servico' -WorkingDirectory $pasta
    $cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
    if ($semSenha) {
        $gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
        $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilho -Settings $cfg -Principal $principal -Force | Out-Null
    } else {
        $gatilho = New-ScheduledTaskTrigger -AtStartup
        Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilho -Settings $cfg -User $usuario -Password $plana -RunLevel Limited -Force | Out-Null
    }
    $plana = $null
    Start-ScheduledTask -TaskName $Nome
    Write-Host 'Ligando o site...' -ForegroundColor Cyan
    $ok = $false
    for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
        Start-Sleep -Seconds 1
        $c = New-Object Net.Sockets.TcpClient
        try { $c.Connect('127.0.0.1', $porta); $ok = $true } catch { } finally { $c.Close() }
    }
    if ($ok) {
        Write-Host ''; Write-Host 'PRONTO! O Exato Web agora liga sozinho, sem janela preta.' -ForegroundColor Green
        Write-Host "Abra: http://127.0.0.1:$porta (com http, sem o s)   (ou o endereco que voce ja usava)"
        Write-Host "Pasta do site: $pasta"
        Write-Host 'Para atualizar: rode PARAR_SITE.bat, troque a pasta "web" e rode LIGAR_SITE.bat.'
    } else {
        Write-Host 'A tarefa foi criada, mas o site nao respondeu em 30 segundos.' -ForegroundColor Yellow
        Write-Host 'Veja o registro com VER_REGISTRO_DO_SITE.bat e me envie as ultimas linhas.'
    }
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
}
Pausa
