@echo off
rem Pede permissao de administrador e coloca o Exato Web num endereco com cadeado (so rede do escritorio).
net session >nul 2>nul
if %errorlevel% neq 0 (
  echo Pedindo permissao de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_ENDERECO_COMERCIAL.ps1"
