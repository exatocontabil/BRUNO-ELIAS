@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0..\programa"
cls
echo ============================================================
echo   EXATO CENTRAL FISCAL V190
echo   Abertura com diagnostico (para o suporte)
echo ============================================================
echo.
echo Dados persistentes: %LOCALAPPDATA%\Exato\Central Fiscal\Dados
echo.
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -3"
)
if not defined PYEXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /i "\WindowsApps\" >nul
        if errorlevel 1 (
            "%%P" -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
            if not errorlevel 1 (set "PYEXE=%%P" & goto :run)
        )
    )
)
if not defined PYEXE (
    echo [ERRO] Python 3.12+ nao foi encontrado. Instale o Python 3.12 ou superior em python.org e marque "Add python.exe to PATH".
    pause
    exit /b 1
)
:run
echo Python selecionado: %PYEXE%
echo Iniciando o aplicativo...
echo.
%PYEXE% -B "%~dp0..\programa\exato_central_fiscal.py"
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" echo [ERRO] Aplicativo encerrado com codigo %ERR%.
echo.
pause
exit /b %ERR%
