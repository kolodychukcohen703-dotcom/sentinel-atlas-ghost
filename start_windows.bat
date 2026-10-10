@echo off
title Sentinel Atlas + Ghost Collaboration
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
set ATLAS_URL=http://127.0.0.1:5010
set GHOST_HUB_URL=http://127.0.0.1:5011
start "Ghost Sentinel Hub" /D "%~dp0ghost_hub" "%~dp0.venv\Scripts\python.exe" ghost_hub.py
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5010/
python app.py
pause
