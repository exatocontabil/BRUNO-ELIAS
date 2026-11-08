@echo off
cd /d "%~dp0"
set EXATO_WEB_HTTPS=1
python -m uvicorn --factory web.app:app_producao --host 127.0.0.1 --port 8443 --proxy-headers
