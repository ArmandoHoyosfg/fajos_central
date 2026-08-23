@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Fajos Central
echo.
echo  Fajos Piteados Central — iniciando...
echo.

REM Preferir pythonw del venv (sin consola negra persistente al abrir el launcher)
set "VENV_W=%~dp0.venv\Scripts\pythonw.exe"
set "VENV_C=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_W%" (
  start "" "%VENV_W%" "%~dp0launcher.py"
  exit /b 0
)

if exist "%VENV_C%" (
  "%VENV_C%" "%~dp0launcher.py"
  exit /b %ERRORLEVEL%
)

REM Sin venv: intentar py launcher / python del PATH
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  echo No hay .venv — usando py -3. Ejecuta setup_windows.ps1 cuando puedas.
  py -3 "%~dp0launcher.py"
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  echo No hay .venv — usando python del PATH.
  python "%~dp0launcher.py"
  exit /b %ERRORLEVEL%
)

echo.
echo  ERROR: No se encontro Python ni .venv
echo  Ejecuta en PowerShell 7:
echo    pwsh -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
echo.
pause
exit /b 1
