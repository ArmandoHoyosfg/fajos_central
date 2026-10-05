@echo off
REM Evita el error "not digitally signed" usando Bypass solo para este script
cd /d "%~dp0"
echo Fajos Central — setup Windows
echo.
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" %*
)
echo.
pause
