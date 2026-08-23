#Requires -Version 7
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "=== Verificar entorno Fajos Central ===" -ForegroundColor Cyan
$ok = 0; $bad = 0
function Check($name, $cond, $hint) {
    if ($cond) {
        Write-Host "  [OK] $name" -ForegroundColor Green
        $script:ok++
    } else {
        Write-Host "  [ ] $name -- $hint" -ForegroundColor Yellow
        $script:bad++
    }
}
$venvPy = Test-Path ".\.venv\Scripts\python.exe"
Check "venv Python" $venvPy "Ejecuta setup_windows.ps1"
Check "launcher.py" (Test-Path ".\launcher.py") "Carpeta incorrecta"
Check "config.ini" (Test-Path ".\config.ini") "Copia config.ini.example"
Check "app/main.py" (Test-Path ".\app\main.py") ""
Check "schema SQL" (Test-Path ".\db\schema") ""
if ($venvPy) {
    & .\.venv\Scripts\python.exe -c "import fastapi, mysql.connector, openpyxl; print('ok')" 2>$null
    Check "Dependencias Python" ($LASTEXITCODE -eq 0) "pip install -r requirements.txt"
}
Write-Host "Resumen: $ok ok, $bad pendientes" -ForegroundColor Cyan
