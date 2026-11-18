@echo off
rem Liga o Exato Web escondido (sem esperar o Windows reiniciar).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-ScheduledTask -TaskName 'Exato Web'; Write-Host 'Ligando... em alguns segundos o site responde.'"
pause
