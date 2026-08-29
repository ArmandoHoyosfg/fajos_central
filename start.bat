@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "LAUNCHER=%~dp0launcher.py"
set "VBS=%~dp0start_silent.vbs"
set "VENV_W=%~dp0.venv\Scripts\pythonw.exe"
set "VENV_C=%~dp0.venv\Scripts\python.exe"

REM 1) venv pythonw (ideal)
if exist "%VENV_W%" (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "%VENV_W%" "%LAUNCHER%"
  ) else (
    start "" "%VENV_W%" "%LAUNCHER%"
  )
  exit /b 0
)

REM 2) pyw launcher (Windows, sin consola)
where pyw >nul 2>&1
if %ERRORLEVEL%==0 (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "pyw" "-3" "%LAUNCHER%"
  ) else (
    start "" pyw -3 "%LAUNCHER%"
  )
  exit /b 0
)

REM 3) pythonw en PATH
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "pythonw" "%LAUNCHER%"
  ) else (
    start "" pythonw "%LAUNCHER%"
  )
  exit /b 0
)

REM 4) venv python (ultima opcion silenciosa via VBS)
if exist "%VENV_C%" (
  if exist "%VBS%" (
    wscript //nologo "%VBS%" "%VENV_C%" "%LAUNCHER%"
  ) else (
    start "" "%VENV_C%" "%LAUNCHER%"
  )
  exit /b 0
)

REM 5) Fallo real: solo entonces mostrar mensaje
if exist "%VBS%" (
  REM intentar py -3 oculto
  where py >nul 2>&1
  if %ERRORLEVEL%==0 (
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
