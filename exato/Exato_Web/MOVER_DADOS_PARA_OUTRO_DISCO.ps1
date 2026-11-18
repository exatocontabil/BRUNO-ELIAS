# Move os dados do Exato Web (banco, usuarios, cofre dos certificados, registros) para outro disco, com seguranca.
# Copia, confere, aponta o site para a pasta nova e deixa a pasta antiga renomeada para voce apagar DEPOIS de ver que tudo funciona.
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
function GB($b) { [math]::Round($b / 1GB, 2) }
try {
    $pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
    Write-Host '=== Exato Web: mover os dados para outro disco ===' -ForegroundColor Cyan
    if ($pasta.StartsWith('\\')) { throw 'Rode a partir da pasta do site neste computador (ex.: C:\ExatoWeb), nao da pasta de rede.' }
    $origem = $env:EXATO_WEB_DADOS
    if (-not $origem -and (Test-Path (Join-Path $pasta 'dados.txt'))) { $origem = (Get-Content (Join-Path $pasta 'dados.txt') | Select-Object -First 1).Trim() }
    if (-not $origem) { $origem = Join-Path $HOME 'ExatoWebDados' }
    if (-not (Test-Path $origem)) { throw "Nao encontrei a pasta de dados atual: $origem" }
    $tam = (Get-ChildItem $origem -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Write-Host "Pasta atual dos dados: $origem  ($(GB $tam) GB)"
    Write-Host ''
    Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { Write-Host ("  {0}  livre {1} GB de {2} GB" -f $_.DeviceID, (GB $_.FreeSpace), (GB $_.Size)) }
    Write-Host ''
    $dest = Read-Host 'Pasta nova (ex.: D:\ExatoWebDados)'
    $dest = $dest.Trim().Trim('"')
    if (-not $dest) { throw 'Nenhuma pasta informada.' }
    if ($dest.StartsWith('\\')) { throw 'O banco nao deve ficar em pasta de rede (pode corromper). Escolha um disco deste computador.' }
    if ($dest.TrimEnd('\') -ieq $origem.TrimEnd('\')) { throw 'A pasta nova e igual a atual.' }
    if (Test-Path $dest) { if (Get-ChildItem $dest -Force | Select-Object -First 1) { throw "A pasta $dest ja tem arquivos. Escolha uma pasta vazia ou nova." } }
    $raiz = [IO.Path]::GetPathRoot($dest); $disco = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($raiz.TrimEnd('\'))'"
    if (-not $disco -or $disco.DriveType -ne 3) { throw "O disco $raiz nao e um disco local deste computador." }
    if ($disco.FreeSpace -lt ($tam * 1.3 + 1GB)) { throw "O disco $raiz nao tem espaco suficiente (livre $(GB $disco.FreeSpace) GB; preciso de pelo menos $(GB ($tam * 1.3 + 1GB)) GB)." }
    $ok = Read-Host "Vou DESLIGAR o site, copiar os dados para $dest e ligar de novo. Continuar? (S/N)"
    if ($ok -notmatch '^[sS]') { throw 'Cancelado. Nada foi alterado.' }

    Write-Host 'Desligando o site...' -ForegroundColor Cyan
    foreach ($t in 'Exato Web Endereco', 'Exato Web') { Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue }
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    $pidf = Join-Path $origem 'servidor.pid'
    if (Test-Path $pidf) { Stop-Process -Id ([int](Get-Content $pidf)) -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3

    Write-Host 'Copiando (pode demorar; nao feche a janela)...' -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    robocopy $origem $dest /E /COPY:DAT /DCOPY:DAT /R:2 /W:5 /NFL /NDL /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "A copia falhou (codigo $LASTEXITCODE). Nada foi apagado; o site continua apontando para a pasta antiga." }
    $a = Get-ChildItem $origem -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    $b = Get-ChildItem $dest -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    if ($a.Count -ne $b.Count -or $a.Sum -ne $b.Sum) { throw "A conferencia da copia nao bateu (arquivos $($a.Count) x $($b.Count)). Nada foi apagado; o site continua na pasta antiga." }
    Write-Host "Copia conferida: $($b.Count) arquivos, $(GB $b.Sum) GB." -ForegroundColor Green

    Set-Content -Path (Join-Path $pasta 'dados.txt') -Value $dest -Encoding ASCII
    if ($env:EXATO_WEB_DADOS) { [Environment]::SetEnvironmentVariable('EXATO_WEB_DADOS', $null, 'User') }
    $antiga = $origem.TrimEnd('\') + '_ANTIGA_apagar_depois'
    $nomeAntigo = Split-Path $antiga -Leaf
    Rename-Item -LiteralPath $origem -NewName $nomeAntigo

    Write-Host 'Ligando o site na pasta nova...' -ForegroundColor Cyan
    Start-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue
    if (Get-ScheduledTask -TaskName 'Exato Web Endereco' -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName 'Exato Web Endereco' }
    $ligou = $false
    for ($i = 0; $i -lt 40 -and -not $ligou; $i++) { Start-Sleep -Seconds 1; $c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 8443); $ligou = $true } catch { } finally { $c.Close() } }
    Write-Host ''
    if ($ligou) {
        Write-Host 'PRONTO! O site agora usa a pasta nova.' -ForegroundColor Green
        Write-Host "  Dados novos: $dest"
        Write-Host "  Pasta antiga (renomeada): $antiga"
        Write-Host 'Confira que tudo funciona (entrar, ver empresas e notas, abrir um certificado). So DEPOIS apague a pasta antiga para liberar o espaco do C:.' -ForegroundColor Yellow
    } else {
        Write-Host 'Os dados foram copiados, mas o site nao respondeu em 40 segundos.' -ForegroundColor Yellow
        Write-Host 'Use VER_REGISTRO_DO_SITE.bat. Para voltar atras: apague o arquivo dados.txt da pasta do site e renomeie a pasta antiga para o nome original.'
    }
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
}
Pausa
