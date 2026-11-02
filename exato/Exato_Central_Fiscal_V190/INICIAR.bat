@echo off
rem Exato Central Fiscal V190 - abre o programa sem a janela preta do console.
setlocal EnableExtensions
cd /d "%~dp0programa"
set "PYW="
where pyw >nul 2>&1
if not errorlevel 1 (
    pyw -3 -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
    if not errorlevel 1 set "PYW=pyw -3"
)
if not defined PYW (
    for /f "delims=" %%P in ('where pythonw 2^>nul') do (
        echo %%P | findstr /i "\WindowsApps\" >nul
        if errorlevel 1 (
            "%%P" -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
            if not errorlevel 1 (set "PYW=%%P" & goto :abrir)
        )
    )
)
if not defined PYW goto :diagnostico
:abrir
start "" %PYW% -B "%~dp0programa\exato_central_fiscal.py"
exit /b 0
:diagnostico
rem Python 3.12+ nao encontrado sem console: abre a versao com mensagens para mostrar o motivo.
call "%~dp0ferramentas\EXECUTAR_COM_DIAGNOSTICO.bat"
exit /b %ERRORLEVEL%
