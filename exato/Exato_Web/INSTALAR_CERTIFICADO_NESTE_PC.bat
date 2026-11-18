@echo off
rem Instala o certificado do escritorio neste computador (uma vez).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_CERTIFICADO_NESTE_PC.ps1"
