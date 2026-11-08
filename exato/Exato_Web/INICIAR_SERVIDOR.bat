@echo off
cd /d "%~dp0"
set EXATO_WEB_HTTPS=1
python -m uvicorn --factory web.app:criar_app --host 127.0.0.1 --port 8443 --proxy-headers
