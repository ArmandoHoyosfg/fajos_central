@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Si nos llaman desde un acceso / Startup, delegar YA a VBS (cierra esta consola).
if /I not "%~1"=="_inner" (
  if exist "%~dp0start_startup.vbs" (
    start "" wscript //nologo "%~dp0start_startup.vbs"
    exit /b 0
  )
  if exist "%~dp0start_silent.vbs" (
    goto :legacy_silent
  )
)

:legacy_silent
set "LAUNCHER=%~dp0launcher.py"
set "VBS=%~dp0start_silent.vbs"
set "VENV_W=%~dp0.venv\Scripts\pythonw.exe"
set "VENV_C=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_W%" (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "%VENV_W%" "%LAUNCHER%"
  ) else (
    start "" "%VENV_W%" "%LAUNCHER%"
  )
  exit /b 0
)

where pyw >nul 2>&1
if %ERRORLEVEL%==0 (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "pyw" "-3" "%LAUNCHER%"
  ) else (
    start "" pyw -3 "%LAUNCHER%"
  )
  exit /b 0
)

where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "pythonw" "%LAUNCHER%"
  ) else (
    start "" pythonw "%LAUNCHER%"
  )
  exit /b 0
)

if exist "%VENV_C%" (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "%VENV_C%" "%LAUNCHER%"
  ) else (
    start "" /b "%VENV_C%" "%LAUNCHER%"
  )
  exit /b 0
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "py" "-3" "%LAUNCHER%"
    exit /b 0
  )
)

echo.
echo  Fajos Central: no se encontro Python.
echo  Ejecuta setup_windows.ps1 una vez para crear el entorno.
echo.
pause
exit /b 1
