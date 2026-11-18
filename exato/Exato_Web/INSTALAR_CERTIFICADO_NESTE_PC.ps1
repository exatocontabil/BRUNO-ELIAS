# Faz ESTE computador confiar no certificado do escritorio (o cadeado do Exato Web aparece sem aviso). Rodar uma vez em cada computador.
$ErrorActionPreference = 'Stop'
function Pausa { Write-Host ''; Read-Host 'Pressione Enter para fechar' | Out-Null }
try {
    $pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
    $crt = Join-Path $pasta 'CERTIFICADO_DO_ESCRITORIO.crt'; $end = Join-Path $pasta 'endereco.txt'
    if (-not (Test-Path $crt) -or -not (Test-Path $end)) { throw 'Faltam arquivos nesta pasta (CERTIFICADO_DO_ESCRITORIO.crt e endereco.txt). Copie a pasta inteira "para_os_outros_pcs".' }
    $d = Get-Content $end; $nome = $d[0].Trim(); $ip = $d[1].Trim()
    Write-Host "Este computador vai confiar no certificado do escritorio e abrir https://$nome" -ForegroundColor Cyan
    Import-Certificate -FilePath $crt -CertStoreLocation Cert:\CurrentUser\Root | Out-Null          # o Windows pode pedir uma confirmacao: clique em Sim
    Write-Host 'Certificado instalado.' -ForegroundColor Green
    $resolve = $null; try { $resolve = (Resolve-DnsName $nome -Type A -ErrorAction Stop | Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress } catch { }
    if ($resolve -eq $ip) { Write-Host "O nome ja aponta para $ip. Nada mais a fazer." -ForegroundColor Green }
    else {
        Write-Host "O nome ainda nao aponta para $ip na rede (o registro no painel do dominio pode nao existir ainda)." -ForegroundColor Yellow
        $r = Read-Host 'Registrar o nome neste computador (arquivo hosts)? (S/N, Enter = S)'
        if (-not $r -or $r -match '^[sS]') {
            $cmd = "`$h='$env:SystemRoot\System32\drivers\etc\hosts'; `$l=@(Get-Content `$h | Where-Object { `$_ -notmatch [regex]::Escape('$nome') }); `$l += '$ip`t$nome'; Set-Content -Path `$h -Value `$l -Encoding ASCII"
            Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd
            Write-Host 'Nome registrado neste computador.' -ForegroundColor Green
        }
    }
    Write-Host ''; Write-Host "PRONTO. Feche e abra o navegador e entre em https://$nome" -ForegroundColor Green
} catch {
    Write-Host ''; Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
}
Pausa
