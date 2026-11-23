@echo off
rem Atualiza o Exato Web com um clique. Copia o atualizador para a pasta temporaria (para poder se atualizar sem se atrapalhar) e roda.
copy /y "%~dp0ATUALIZAR_SITE.ps1" "%TEMP%\exato_atualizar.ps1" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\exato_atualizar.ps1" -Pasta "%~dp0."
