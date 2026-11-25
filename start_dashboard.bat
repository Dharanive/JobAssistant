@echo off
title Naukri Assistant Dashboard
cd /d "%~dp0"
echo Starting Naukri Assistant Web Dashboard...
echo Open your browser at http://localhost:5000
start http://localhost:5000
python app.py
pause
