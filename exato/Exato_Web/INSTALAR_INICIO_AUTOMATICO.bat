@echo off
rem Pede permissao de administrador e roda o instalador (liga o site sozinho com o Windows, sem janela preta).
net session >nul 2>nul
if %errorlevel% neq 0 (
  echo Pedindo permissao de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_INICIO_AUTOMATICO.ps1"
