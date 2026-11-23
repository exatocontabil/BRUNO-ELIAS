# Atualiza o Exato Web com UM clique: acha o pacote novo (ZIP), desliga o site, troca os arquivos, religa e confere.
# Se o site nao subir, volta sozinho para a versao anterior. Nao mexe nos dados, no cofre, no endereco (Caddy) nem no dados.txt.
param([string]$Pasta)
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
function Responde { $c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 8443); return $true } catch { return $false } finally { $c.Close() } }
function Desligar {
    foreach ($t in 'Exato Web Endereco', 'Exato Web') { Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue }
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    $dados = $env:EXATO_WEB_DADOS
    if (-not $dados -and (Test-Path (Join-Path $Pasta 'dados.txt'))) { $dados = (Get-Content (Join-Path $Pasta 'dados.txt') | Select-Object -First 1).Trim() }
    if (-not $dados) { $dados = Join-Path $HOME 'ExatoWebDados' }
    $p = Join-Path $dados 'servidor.pid'; if (Test-Path $p) { Stop-Process -Id ([int](Get-Content $p)) -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
}
function Ligar {
    Start-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue
    if (Get-ScheduledTask -TaskName 'Exato Web Endereco' -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName 'Exato Web Endereco' }
    for ($i = 0; $i -lt 45; $i++) { Start-Sleep -Seconds 1; if (Responde) { return $true } }
    return $false
}
try {
    Write-Host '=== Exato Web: atualizar ===' -ForegroundColor Cyan
    if (-not $Pasta) { $Pasta = Split-Path -Parent $MyInvocation.MyCommand.Path }
    $Pasta = [IO.Path]::GetFullPath($Pasta).TrimEnd('\')
    if ($Pasta.StartsWith('\\')) { throw 'Rode a partir da pasta do site neste computador (ex.: C:\ExatoWeb), nao da pasta de rede.' }
    if (-not (Test-Path (Join-Path $Pasta 'web\app.py'))) { throw "Esta nao parece a pasta do site: $Pasta" }
    $instalada = 'desconhecida'; if (Test-Path (Join-Path $Pasta 'VERSAO.txt')) { $instalada = (Get-Content (Join-Path $Pasta 'VERSAO.txt') | Select-Object -First 1).Trim() }
    Write-Host "Versao instalada: $instalada"

    # 1) acha o pacote novo
    $cand = @()
    foreach ($d in (Join-Path $env:USERPROFILE 'Downloads'), (Join-Path $env:USERPROFILE 'Desktop'), $Pasta) { if (Test-Path $d) { $cand += Get-ChildItem $d -Filter 'Exato_Web_*.zip' -File -ErrorAction SilentlyContinue } }
    $zip = $null
    if ($cand) {
        $novo = $cand | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        Write-Host ("Pacote mais novo encontrado: {0}  ({1})" -f $novo.FullName, $novo.LastWriteTime.ToString('dd/MM/yyyy HH:mm'))
        $r = Read-Host 'Usar este? (Enter = sim, ou digite o caminho de outro ZIP)'
        if ($r) { $zip = $r.Trim().Trim('"') } else { $zip = $novo.FullName }
    } else {
        $zip = (Read-Host 'Nao achei nenhum Exato_Web_*.zip em Downloads. Caminho completo do ZIP').Trim().Trim('"')
    }
    if (-not (Test-Path $zip -PathType Leaf)) { throw "Nao encontrei o arquivo: $zip" }

    # 2) abre o pacote numa pasta temporaria e confere
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $tmp = Join-Path $env:TEMP ('exato_atualizacao_' + (Get-Date -Format 'yyyyMMddHHmmss'))
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)
    $fonte = Join-Path $tmp 'Exato_Web'
    if (-not (Test-Path (Join-Path $fonte 'web\app.py')) -or -not (Test-Path (Join-Path $fonte 'nucleo'))) { throw 'Este ZIP nao parece um pacote do Exato Web (faltam web e nucleo).' }
    $nova = 'desconhecida'; if (Test-Path (Join-Path $fonte 'VERSAO.txt')) { $nova = (Get-Content (Join-Path $fonte 'VERSAO.txt') | Select-Object -First 1).Trim() }
    Write-Host "Versao nova: $nova" -ForegroundColor Green
    $r = Read-Host 'Atualizar agora? O site fica fora do ar por 1 ou 2 minutos. (Enter = sim, N = cancelar)'
    if ($r -match '^[nN]') { Remove-Item $tmp -Recurse -Force; throw 'Cancelado. Nada foi alterado.' }

    # 3) guarda a versao atual (para voltar atras) e desliga
    Write-Host 'Desligando o site...' -ForegroundColor Cyan
    Desligar
    $ant = Join-Path $Pasta '_versao_anterior'
    if (Test-Path $ant) { Remove-Item $ant -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $ant | Out-Null
    foreach ($d in 'web', 'nucleo', 'docs') { if (Test-Path (Join-Path $Pasta $d)) { robocopy (Join-Path $Pasta $d) (Join-Path $ant $d) /E /NFL /NDL /NJH /NJS /NP | Out-Null } }
    foreach ($f in Get-ChildItem $Pasta -File) { Copy-Item $f.FullName $ant -Force }
    $reqAntes = (Get-FileHash (Join-Path $Pasta 'requirements.txt') -ErrorAction SilentlyContinue).Hash

    # 4) troca os arquivos (web, nucleo e docs sao espelhados; os arquivos da raiz sao copiados por cima; dados.txt, caddy e para_os_outros_pcs ficam como estao)
    Write-Host 'Trocando os arquivos...' -ForegroundColor Cyan
    foreach ($d in 'web', 'nucleo', 'docs') {
        if (Test-Path (Join-Path $fonte $d)) { robocopy (Join-Path $fonte $d) (Join-Path $Pasta $d) /MIR /NFL /NDL /NJH /NJS /NP | Out-Null; if ($LASTEXITCODE -ge 8) { throw "Falha ao copiar a pasta $d." } }
    }
    foreach ($f in Get-ChildItem $fonte -File) { Copy-Item $f.FullName $Pasta -Force }
    $reqDepois = (Get-FileHash (Join-Path $Pasta 'requirements.txt') -ErrorAction SilentlyContinue).Hash
    if ($reqAntes -ne $reqDepois) {
        Write-Host 'Dependencias mudaram: instalando...' -ForegroundColor Cyan
        $py = $null; if (Get-Command py -ErrorAction SilentlyContinue) { $py = 'py' } else { $py = 'python' }
        $ErrorActionPreference = 'Continue'
        if ($py -eq 'py') { & py -3 -m pip install -q -r (Join-Path $Pasta 'requirements.txt') } else { & python -m pip install -q -r (Join-Path $Pasta 'requirements.txt') }
        $ErrorActionPreference = 'Stop'
    }

    # 5) liga e confere; se nao subir, volta para a versao anterior
    Write-Host 'Ligando o site...' -ForegroundColor Cyan
    if (Ligar) {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host ''; Write-Host "PRONTO! Exato Web atualizado para: $nova" -ForegroundColor Green
        Write-Host 'No navegador, aperte Ctrl+F5 para ver a versao nova.'
        Write-Host "A versao anterior ficou em $ant (para voltar atras, se precisar)."
    } else {
        Write-Host 'O site nao respondeu com a versao nova. Voltando para a versao anterior...' -ForegroundColor Yellow
        Desligar
        foreach ($d in 'web', 'nucleo', 'docs') { if (Test-Path (Join-Path $ant $d)) { robocopy (Join-Path $ant $d) (Join-Path $Pasta $d) /MIR /NFL /NDL /NJH /NJS /NP | Out-Null } }
        foreach ($f in Get-ChildItem $ant -File) { Copy-Item $f.FullName $Pasta -Force }
        if (Ligar) { Write-Host 'A versao anterior voltou a funcionar. A atualizacao NAO foi aplicada.' -ForegroundColor Yellow } else { Write-Host 'Nem a versao anterior respondeu. Use VER_REGISTRO_DO_SITE.bat e me envie as ultimas linhas.' -ForegroundColor Red }
        Write-Host 'Me envie as ultimas linhas do registro (VER_REGISTRO_DO_SITE.bat) para eu corrigir a versao nova.'
    }
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    if ($Pasta -and -not (Responde)) { Write-Host 'O site esta desligado. Rode LIGAR_SITE.bat se precisar.' -ForegroundColor Yellow }
}
Pausa
