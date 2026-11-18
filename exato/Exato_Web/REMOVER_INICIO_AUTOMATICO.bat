@echo off
rem Volta ao modo antigo (janela preta com INICIAR_SERVIDOR.bat): remove a tarefa "Exato Web".
net session >nul 2>nul
if %errorlevel% neq 0 ( powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b )
powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-ScheduledTask -TaskName 'Exato Web' -ErrorAction SilentlyContinue; Stop-ScheduledTask -TaskName 'Exato Web Endereco' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'Exato Web Endereco' -Confirm:$false -ErrorAction SilentlyContinue; Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force; Unregister-ScheduledTask -TaskName 'Exato Web' -Confirm:$false -ErrorAction SilentlyContinue; $p=Join-Path $HOME 'ExatoWebDados\servidor.pid'; if(Test-Path $p){ Stop-Process -Id ([int](Get-Content $p)) -Force -ErrorAction SilentlyContinue }; Write-Host 'Pronto: o site nao liga mais sozinho.'"
pause
