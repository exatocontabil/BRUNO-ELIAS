@echo off
rem Desliga o Exato Web (o que roda escondido). Use antes de trocar a pasta "web" por uma versao nova.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue; $p=Join-Path $HOME 'ExatoWebDados\servidor.pid'; if(Test-Path $p){ $id=[int](Get-Content $p); Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }; Write-Host 'Site desligado.'"
pause
