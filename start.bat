@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Preferir arranque SIN consola (pythonw + VBS)
set "VENV_W=%~dp0.venv\Scripts\pythonw.exe"
set "VENV_C=%~dp0.venv\Scripts\python.exe"
set "LAUNCHER=%~dp0launcher.py"
set "VBS=%~dp0start_silent.vbs"

if exist "%VENV_W%" (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "%VENV_W%" "%LAUNCHER%"
  ) else (
    start "" "%VENV_W%" "%LAUNCHER%"
  )
  exit /b 0
)

if exist "%VENV_C%" (
  REM Con consola solo si no hay pythonw
  "%VENV_C%" "%LAUNCHER%"
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [Aviso] No hay .venv — usando py. Preferible: setup_windows.ps1
  py -3 "%LAUNCHER%"
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [Aviso] No hay .venv — usando python del PATH
  python "%LAUNCHER%"
  exit /b %ERRORLEVEL%
)

echo ERROR: No se encontro Python ni .venv
echo Ejecuta: pwsh -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
pause
exit /b 1
