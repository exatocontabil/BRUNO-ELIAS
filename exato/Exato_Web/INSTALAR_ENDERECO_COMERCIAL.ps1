# Coloca o Exato Web num endereco bonito, so para o escritorio, com cadeado (HTTPS): https://fiscal.exatosolucoescontabeis.com
# Usa o Caddy (programa pequeno e gratuito) com certificado do proprio escritorio. Rode pelo INSTALAR_ENDERECO_COMERCIAL.bat (administrador).
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
try {
    Write-Host '=== Exato Web: endereco do escritorio com cadeado ===' -ForegroundColor Cyan
    $pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
    if ($pasta.StartsWith('\\')) { throw 'Rode este instalador a partir da pasta DESTE computador (por exemplo C:\ExatoWeb), nao da pasta de rede. Copie o pacote novo para C:\ExatoWeb e rode de la.' }
    $padrao = 'fiscal.exatosolucoescontabeis.com'
    $nome = Read-Host "Endereco desejado (Enter = $padrao)"
    if (-not $nome) { $nome = $padrao }
    $nome = $nome.Trim().ToLower()
    if ($nome -notmatch '^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$') { throw "Endereco invalido: $nome" }

    # IP deste computador na rede do escritorio
    $rota = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1
    $ip = (Get-NetIPAddress -InterfaceIndex $rota.InterfaceIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
    if (-not $ip) { throw 'Nao consegui descobrir o IP deste computador. Conecte-se a rede do escritorio e tente de novo.' }
    Write-Host "IP deste computador: $ip" -ForegroundColor Green

    # Caddy
    $cdir = Join-Path $pasta 'caddy'; New-Item -ItemType Directory -Force -Path $cdir | Out-Null
    $exe = Join-Path $cdir 'caddy.exe'
    if (-not (Test-Path $exe)) {
        Write-Host 'Baixando o Caddy (site oficial)...' -ForegroundColor Cyan
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -UseBasicParsing -Uri 'https://caddyserver.com/api/download?os=windows&arch=amd64' -OutFile $exe
        } catch {
            Remove-Item $exe -ErrorAction SilentlyContinue
            throw "Nao consegui baixar o Caddy. Baixe manualmente em https://caddyserver.com/download (Windows, amd64), salve como $exe e rode este instalador de novo."
        }
    }
    $ErrorActionPreference = 'Continue'          # programas externos escrevem avisos na saida de erro; isso nao e falha
    & $exe version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "O arquivo $exe nao funciona. Apague-o e rode de novo." }

    $dados = Join-Path $cdir 'dados'; New-Item -ItemType Directory -Force -Path $dados | Out-Null
    $conf = @"
{
	auto_https disable_redirects
}
$nome {
	tls internal
	encode gzip
	reverse_proxy 127.0.0.1:8443
}
"@
    Set-Content -Path (Join-Path $cdir 'Caddyfile') -Value $conf -Encoding ASCII
    & $exe validate --config (Join-Path $cdir 'Caddyfile') --adapter caddyfile 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'A configuracao do Caddy nao passou na conferencia.' }
    $ErrorActionPreference = 'Stop'

    # Roda escondido: um VBS (sem janela, sem piscar) liga o Caddy.
    $vbs = @"
Set sh = CreateObject("WScript.Shell")
sh.Environment("Process")("XDG_DATA_HOME") = "$dados"
sh.Environment("Process")("XDG_CONFIG_HOME") = "$dados"
sh.CurrentDirectory = "$cdir"
sh.Run """$exe"" run --config ""$cdir\Caddyfile"" --adapter caddyfile", 0, False
"@
    Set-Content -Path (Join-Path $cdir 'iniciar_caddy.vbs') -Value $vbs -Encoding ASCII

    # Usuario da tarefa: o mesmo do site (a tarefa "Exato Web").
    $tarefaSite = Get-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue
    if (-not $tarefaSite) { throw 'Instale antes o inicio automatico do site (INSTALAR_INICIO_AUTOMATICO.bat).' }
    $usuario = $tarefaSite.Principal.UserId
    $acao = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + (Join-Path $cdir 'iniciar_caddy.vbs') + '"') -WorkingDirectory $cdir
    $cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
    $gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'Exato Web Endereco' -Action $acao -Trigger $gatilho -Settings $cfg -Principal $principal -Force | Out-Null

    # Firewall: so a rede do escritorio entra na porta 443.
    Get-NetFirewallRule -DisplayName 'Exato Web (endereco do escritorio)' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName 'Exato Web (endereco do escritorio)' -Direction Inbound -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Action Allow -Profile Any | Out-Null

    # Este computador tambem enxerga o nome, mesmo antes do registro existir no painel do dominio.
    $hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
    $linhas = @(Get-Content $hosts | Where-Object { $_ -notmatch [regex]::Escape($nome) })
    $linhas += "$ip`t$nome"
    Set-Content -Path $hosts -Value $linhas -Encoding ASCII

    Write-Host 'Ligando o endereco...' -ForegroundColor Cyan
    Start-ScheduledTask -TaskName 'Exato Web Endereco'
    $crt = Join-Path $dados 'caddy\pki\authorities\local\root.crt'
    for ($i = 0; $i -lt 40 -and -not (Test-Path $crt); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Test-Path $crt)) { throw 'O Caddy nao criou o certificado do escritorio. Veja a pasta caddy\dados e tente de novo.' }

    # Confia no certificado neste computador e prepara a pasta para os outros.
    certutil -addstore -f Root $crt | Out-Null
    $out = Join-Path $pasta 'para_os_outros_pcs'; New-Item -ItemType Directory -Force -Path $out | Out-Null
    Copy-Item $crt (Join-Path $out 'CERTIFICADO_DO_ESCRITORIO.crt') -Force
    Set-Content -Path (Join-Path $out 'endereco.txt') -Value @($nome, $ip) -Encoding ASCII
    foreach ($f in 'INSTALAR_CERTIFICADO_NESTE_PC.bat', 'INSTALAR_CERTIFICADO_NESTE_PC.ps1') { if (Test-Path (Join-Path $pasta $f)) { Copy-Item (Join-Path $pasta $f) $out -Force } }

    Write-Host ''
    Write-Host "PRONTO neste computador. Abra: https://$nome" -ForegroundColor Green
    Write-Host ''
    Write-Host 'FALTAM 2 PASSOS:' -ForegroundColor Yellow
    Write-Host " 1) No cPanel da HostGator > Editor de Zona, crie um registro  Tipo A  |  Nome: $nome  |  Endereco: $ip"
    Write-Host '    (reserve este IP no roteador para ele nao mudar). Enquanto isso nao for feito, so este computador abre o nome.'
    Write-Host " 2) Copie a pasta  $out  para cada outro computador e rode INSTALAR_CERTIFICADO_NESTE_PC.bat la (so uma vez)."
    Start-Process explorer.exe $out
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
}
Pausa
