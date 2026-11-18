@echo off
cd /d "%~dp0"
set EXATO_WEB_HTTPS=1
rem Usa o Python que estiver instalado: primeiro o "py" (o "python" do Windows pode ser so um atalho da Loja), senao o "python" (qualquer versao 3.12 ou mais nova).
where py >nul 2>nul
if %errorlevel%==0 ( set PY=py -3 ) else ( set PY=python )
%PY% -m uvicorn --factory web.app:app_producao --host 127.0.0.1 --port 8443 --proxy-headers
pause
