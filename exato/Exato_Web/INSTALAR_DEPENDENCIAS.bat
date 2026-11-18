@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py -3 )
%PY% --version
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
pause
