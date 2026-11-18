@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 ( set PY=py -3 ) else ( set PY=python )
%PY% --version
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
pause
