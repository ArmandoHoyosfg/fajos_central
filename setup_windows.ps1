#Requires -Version 7
<#
.SYNOPSIS
  Instalación inicial en Windows (PowerShell 7)
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Fajos Central — Setup Windows ===" -ForegroundColor Cyan

# 1. Crear venv
if (-not (Test-Path ".\.venv")) {
    Write-Host "Creando entorno virtual .venv ..."
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        python -m venv .venv
    }
} else {
    Write-Host "Entorno .venv ya existe."
}

# 2. Activar (en esta sesión)
$activate = ".\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Host "No se encontró Activate.ps1" -ForegroundColor Red
    exit 1
}

# Política de ejecución solo para este proceso si hace falta
try {
    & $activate
} catch {
    Write-Host "Aviso: si falla la activación por política, ejecuta una vez:" -ForegroundColor Yellow
    Write-Host '  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned' -ForegroundColor Yellow
    throw
}

# 3. Dependencias
Write-Host "Instalando dependencias..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. .env
if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "Creado .env — edítalo con usuario/contraseña de MariaDB." -ForegroundColor Yellow
} else {
    Write-Host ".env ya existe."
}

Write-Host ""
Write-Host "Listo. Para abrir el launcher:" -ForegroundColor Green
Write-Host "  pwsh -File .\start.ps1"
Write-Host "  o:  python launcher.py"
