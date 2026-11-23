# Restaura uma copia de seguranca do Exato Web (ZIP feito pela tela "Copia de seguranca").
# Nao apaga nada: os dados atuais ficam renomeados (..._ANTES_restauracao_...) para voce voltar atras se precisar.
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
    Write-Host '=== Exato Web: restaurar copia de seguranca ===' -ForegroundColor Cyan
    $dados = $env:EXATO_WEB_DADOS
    if (-not $dados -and (Test-Path (Join-Path $pasta 'dados.txt'))) { $dados = (Get-Content (Join-Path $pasta 'dados.txt') | Select-Object -First 1).Trim() }
    if (-not $dados) { $dados = Join-Path $HOME 'ExatoWebDados' }
    Write-Host "Pasta de dados do site: $dados"
    $zip = (Read-Host 'Caminho completo do ZIP da copia (ex.: E:\CopiaExato\ExatoWeb_backup_20261123_020000.zip)').Trim().Trim('"')
    if (-not (Test-Path $zip -PathType Leaf)) { throw "Nao encontrei o arquivo $zip" }
    if ((Split-Path $zip -Leaf) -notlike 'ExatoWeb_backup_*.zip') { throw 'Este nao parece ser um ZIP de copia do Exato Web (o nome deve comecar com ExatoWeb_backup_).' }
    $z = [IO.Compression.ZipFile]::OpenRead($zip); $n = $z.Entries.Count; $tem = ($z.Entries | Where-Object { $_.FullName -like 'nucleo/*' } | Select-Object -First 1); $z.Dispose()
    if (-not $tem) { throw 'O ZIP nao tem a pasta nucleo (o banco). Nao parece uma copia valida.' }
    Write-Host "ZIP ok: $n arquivos."
    $r = Read-Host "Vou DESLIGAR o site, guardar os dados atuais de lado e colocar os da copia no lugar. Continuar? (S/N)"
    if ($r -notmatch '^[sS]') { throw 'Cancelado. Nada foi alterado.' }
    foreach ($t in 'Exato Web Endereco', 'Exato Web') { Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue }
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    $pidf = Join-Path $dados 'servidor.pid'; if (Test-Path $pidf) { Stop-Process -Id ([int](Get-Content $pidf)) -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    $lado = $dados.TrimEnd('\') + '_ANTES_restauracao_' + (Get-Date -Format 'yyyyMMdd_HHmm')
    if (Test-Path $dados) { Rename-Item -LiteralPath $dados -NewName (Split-Path $lado -Leaf) }
    Write-Host 'Restaurando (pode demorar)...' -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $dados | Out-Null
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $dados)
    Write-Host 'Dados restaurados.' -ForegroundColor Green
    Start-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue
    if (Get-ScheduledTask -TaskName 'Exato Web Endereco' -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName 'Exato Web Endereco' }
    Write-Host ''
    Write-Host 'PRONTO. Entre no site e confira empresas, notas e usuarios.' -ForegroundColor Green
    Write-Host "Os dados de antes da restauracao ficaram em: $lado   (apague so depois de conferir)" -ForegroundColor Yellow
    Write-Host 'Se os certificados nao abrirem (cofre de outro computador/usuario), envie-os de novo na tela Certificados A1.' -ForegroundColor Yellow
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
}
Pausa
