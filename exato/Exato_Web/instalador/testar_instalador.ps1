# Teste de ponta a ponta do instalador no Windows: instala em silencio, confere que o Exato liga sozinho e abre a tela de configuracao,
# desinstala e confere que os dados ficam. Usado pelo GitHub Actions (nao precisa de ninguem na frente do computador).
param([Parameter(Mandatory = $true)][string]$Instalador, [string]$Base = $env:RUNNER_TEMP)
$ErrorActionPreference = 'Stop'
function Rodar($exe, $args2, $limite = 600) {
    # Nao usar Start-Process -Wait: ele tambem espera o site que o instalador deixa ligado (e nunca termina).
    $proc = Start-Process -FilePath $exe -ArgumentList $args2 -PassThru
    if (-not $proc.WaitForExit($limite * 1000)) { try { $proc.Kill() } catch { }; Falha "demorou mais de $limite s: $exe" }
    return $proc.ExitCode
}
function Falha($m) { Write-Host "FALHOU: $m" -ForegroundColor Red; if (Test-Path "$Base\setup.log") { Get-Content "$Base\setup.log" -Tail 60 }; exit 1 }
$alvo = Join-Path $Base 'ExatoWebTeste'; $dados = Join-Path $Base 'ExatoDadosTeste'
Write-Host "Instalando $Instalador em $alvo (dados em $dados)..."
$codigo = Rodar $Instalador "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=`"$alvo`" /DADOS=`"$dados`" /LOG=`"$Base\setup.log`""
if ($codigo -ne 0) { Falha "o instalador saiu com codigo $($codigo)" }
foreach ($f in 'python\pythonw.exe', 'app\web\app.py', 'app\supervisor.py', 'app\dados.txt', 'exato.ico') { if (-not (Test-Path (Join-Path $alvo $f))) { Falha "faltou $f na instalacao" } }
if ((Get-Content (Join-Path $alvo 'app\dados.txt') | Select-Object -First 1).Trim() -ne $dados) { Falha 'dados.txt nao aponta para a pasta escolhida' }
Write-Host 'Esperando o Exato ligar sozinho (ate 120 s)...'
$ok = $false
for ($i = 0; $i -lt 120 -and -not $ok; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8443/saude' -UseBasicParsing -TimeoutSec 3; if ($r.Content -eq 'ok') { $ok = $true } } catch { } }
if (-not $ok) {
    if (Test-Path "$dados\logs\servidor_saida.log") { Write-Host '--- registro do site ---'; Get-Content "$dados\logs\servidor_saida.log" -Tail 60 }
    Falha 'o Exato nao ligou depois da instalacao'
}
Write-Host 'Exato respondeu. Conferindo a primeira abertura...'
$h = [System.Net.Http.HttpClientHandler]::new(); $h.AllowAutoRedirect = $false
$cli = [System.Net.Http.HttpClient]::new($h); $cli.Timeout = [TimeSpan]::FromSeconds(20)
$r = $cli.GetAsync('http://127.0.0.1:8443/login').GetAwaiter().GetResult()
$loc = if ($r.Headers.Location) { $r.Headers.Location.ToString() } else { '' }
$r = [pscustomobject]@{ StatusCode = [int]$r.StatusCode; Headers = @{ Location = $loc } }
if ($r.StatusCode -ne 303 -or "$($r.Headers.Location)" -notlike '*/configurar') { Falha "o /login deveria levar a /configurar (veio $($r.StatusCode) $($r.Headers.Location))" }
$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8443/configurar' -UseBasicParsing
if ($r.StatusCode -ne 200 -or $r.Content -notlike '*Criar o administrador*') { Falha 'a tela de criar o administrador nao abriu' }
if (-not (Test-Path "$dados\supervisor.pid")) { Falha 'o supervisor nao guardou o seu numero de processo' }
Write-Host 'Instalacao ok. Atualizando por cima (mesma versao) para conferir o reinicio...'
$codigo = Rodar $Instalador "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=`"$alvo`" /DADOS=`"$dados`" /LOG=`"$Base\setup2.log`""
if ($codigo -ne 0) { Falha "a atualizacao por cima saiu com codigo $($codigo)" }
$ok = $false
for ($i = 0; $i -lt 120 -and -not $ok; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8443/saude' -UseBasicParsing -TimeoutSec 3; if ($r.Content -eq 'ok') { $ok = $true } } catch { } }
if (-not $ok) { Falha 'o Exato nao voltou depois de atualizar por cima' }
Write-Host 'Atualizando como o site faz (auxiliar atualizar.pyw)...'
# Como no AUXILIAR2: um processo do Exato que NAO esta na lista do desligamento normal e segura os arquivos do Python.
$solto = Start-Process -FilePath (Join-Path $alvo 'python\pythonw.exe') -ArgumentList '-c "import time; time.sleep(900)"' -PassThru
Start-Sleep -Seconds 2
if ($solto.HasExited) { Falha 'nao consegui deixar o processo solto ligado para o teste' }
$ant = "$dados\logs\atualizacao.log"; if (Test-Path $ant) { Remove-Item $ant -Force }
Start-Process -FilePath (Join-Path $alvo 'python\pythonw.exe') -ArgumentList "`"$(Join-Path $alvo 'app\atualizar.pyw')`" `"$Instalador`" `"$alvo`" `"$dados`"" | Out-Null
$fim = $false
for ($i = 0; $i -lt 180 -and -not $fim; $i++) { Start-Sleep -Seconds 1; if (Test-Path $ant) { try { if ((Get-Content $ant -Raw) -match 'Log closed') { $fim = $true } } catch { } } }
if (-not $fim) { Falha 'a atualizacao pelo auxiliar nao terminou' }
if (-not ((Get-Content $ant -Raw) -match 'Installation process succeeded')) { Falha 'a atualizacao pelo auxiliar nao foi concluida (ver o registro acima)' }
if (-not $solto.HasExited) { try { $solto.Kill() } catch { }; Falha 'o instalador nao desligou o processo solto do Exato' }
$ok = $false
for ($i = 0; $i -lt 120 -and -not $ok; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8443/saude' -UseBasicParsing -TimeoutSec 3; if ($r.Content -eq 'ok') { $ok = $true } } catch { } }
if (-not $ok) { Falha 'o Exato nao voltou depois da atualizacao pelo auxiliar' }
Write-Host 'Endereco seguro (cadeado): instalando por cima com um endereco de teste...'
$nomeTeste = 'exato-teste.test'
$codigo = Rodar $Instalador "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=`"$alvo`" /DADOS=`"$dados`" /LOG=`"$Base\setup3.log`" /ENDERECO=`"$nomeTeste`""
if ($codigo -ne 0) { Falha "a instalacao com endereco saiu com codigo $($codigo)" }
$ok = $false
for ($i = 0; $i -lt 150 -and -not $ok; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-WebRequest -Uri "https://$nomeTeste/saude" -UseBasicParsing -TimeoutSec 5; if ($r.Content -eq 'ok') { $ok = $true } } catch { } }
if (-not $ok) {
    if (Test-Path "$dados\logs\endereco.log") { Write-Host '--- registro do endereco ---'; Get-Content "$dados\logs\endereco.log" -Tail 20 }
    if (Test-Path "$dados\caddy\configurado.json") { Get-Content "$dados\caddy\configurado.json" }
    Falha 'o endereco seguro (cadeado) nao abriu depois da instalacao'
}
$cad = Get-Process -Name caddy -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($alvo, [StringComparison]::OrdinalIgnoreCase) }
if (-not $cad) { Falha 'o programa do endereco seguro nao esta ligado' }
Write-Host 'Endereco seguro ok. Instalando de novo com o mesmo endereco (nao deve pedir nada nem refazer)...'
$codigo = Rodar $Instalador "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=`"$alvo`" /DADOS=`"$dados`" /LOG=`"$Base\setup4.log`" /ENDERECO=`"$nomeTeste`""
if ($codigo -ne 0) { Falha "a reinstalacao com endereco saiu com codigo $($codigo)" }
$ok = $false
for ($i = 0; $i -lt 150 -and -not $ok; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-WebRequest -Uri "https://$nomeTeste/saude" -UseBasicParsing -TimeoutSec 5; if ($r.Content -eq 'ok') { $ok = $true } } catch { } }
if (-not $ok) { Falha 'o endereco seguro nao voltou depois de reinstalar' }
Write-Host 'Desinstalando...'
$u = Get-ChildItem $alvo -Filter 'unins*.exe' | Select-Object -First 1
if (-not $u) { Falha 'nao achei o desinstalador' }
$codigo = Rodar $u.FullName '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
Start-Sleep -Seconds 5
$ainda = $false; try { Invoke-WebRequest -Uri 'http://127.0.0.1:8443/saude' -UseBasicParsing -TimeoutSec 3 | Out-Null; $ainda = $true } catch { }
if ($ainda) { Falha 'o Exato continuou ligado depois de desinstalar' }
if (Test-Path (Join-Path $alvo 'python')) { Falha 'a desinstalacao deixou o Python dentro da pasta do programa' }
$sobrou = Get-Process -Name caddy -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($alvo, [StringComparison]::OrdinalIgnoreCase) }
if ($sobrou) { Falha 'a desinstalacao deixou o programa do endereco seguro ligado' }
if (-not (Test-Path $dados)) { Falha 'a desinstalacao apagou a pasta de dados (ela deve ficar)' }
Write-Host 'TUDO CERTO: instala, liga sozinho, atualiza por cima, desinstala e mantem os dados.' -ForegroundColor Green
