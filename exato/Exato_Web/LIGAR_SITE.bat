@echo off
rem Liga o Exato Web escondido (e o endereco com cadeado, se instalado), sem esperar o Windows reiniciar.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-ScheduledTask -TaskName 'Exato Web'; if(Get-ScheduledTask -TaskName 'Exato Web Endereco' -ErrorAction SilentlyContinue){ Start-ScheduledTask -TaskName 'Exato Web Endereco' }; Write-Host 'Ligando... em alguns segundos o site responde.'"
pause
