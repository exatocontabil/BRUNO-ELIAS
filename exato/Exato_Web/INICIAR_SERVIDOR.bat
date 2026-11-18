@echo off
rem pushd funciona tambem quando a pasta esta na rede (\\SERVIDOR\...): cria uma letra de unidade temporaria.
pushd "%~dp0"
set EXATO_WEB_HTTPS=1
rem Se o Windows deixou a pasta "web" como "Web" (maiuscula), o Python nao a acha: aqui ela e corrigida.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Directory | Where-Object { $_.Name -ieq 'web' -and $_.Name -cne 'web' } | ForEach-Object { Rename-Item -LiteralPath $_.FullName -NewName 'web_tmp'; Rename-Item -LiteralPath (Join-Path $_.Parent.FullName 'web_tmp') -NewName 'web' }"
rem Usa o Python que estiver instalado: primeiro o "py" (o "python" do Windows pode ser so um atalho da Loja), senao o "python" (qualquer versao 3.12 ou mais nova).
where py >nul 2>nul
if %errorlevel%==0 ( set PY=py -3 ) else ( set PY=python )
%PY% -m uvicorn --factory web.app:app_producao --host 127.0.0.1 --port 8443 --proxy-headers
popd
pause
