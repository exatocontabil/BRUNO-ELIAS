@echo off
chcp 65001 >nul
echo ============================================================
echo   EXATO - componente para NFS-e por usuario e senha
echo ============================================================
echo.
echo Instalando o componente. Aguarde...
echo.
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE set "PYEXE=python"
%PYEXE% -m pip install --upgrade playwright
echo.
if errorlevel 1 (echo [ERRO] A instalacao nao foi concluida. Chame o suporte.) else (echo Pronto! Abra o Exato novamente.)
echo.
pause
