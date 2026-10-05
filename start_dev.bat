@echo off
REM Arranque CON consola visible (solo diagnostico / DEV)
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Fajos Central DEV console
set "VENV=%~dp0.venv\Scripts\python.exe"
if exist "%VENV%" (
  "%VENV%" "%~dp0launcher.py"
) else (
  py -3 "%~dp0launcher.py" 2>nul || python "%~dp0launcher.py"
)
pause
