@echo off
rem Restaura uma copia de seguranca do Exato Web (nao apaga os dados atuais: ficam de lado).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESTAURAR_BACKUP.ps1"
