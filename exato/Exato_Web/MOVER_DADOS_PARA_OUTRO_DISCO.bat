@echo off
rem Move os dados do Exato Web (banco, usuarios, certificados) para outro disco, com copia conferida. Nao precisa ser administrador.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MOVER_DADOS_PARA_OUTRO_DISCO.ps1"
