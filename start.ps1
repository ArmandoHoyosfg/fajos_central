#Requires -Version 7
<#
.SYNOPSIS
  Arranca el launcher usando el Python del .venv (no el de PATH/Inkscape).
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "No hay .venv válido. Ejecuta primero:" -ForegroundColor Red
    Write-Host "  pwsh -File .\setup_windows.ps1"
    exit 1
}

& $venvPy -c "import sys; print(sys.version)" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "El .venv está roto (Python base movido/borrado). Repara con:" -ForegroundColor Red
    Write-Host "  pwsh -File .\setup_windows.ps1"
    exit 1
}

Write-Host "Iniciando launcher con: $venvPy" -ForegroundColor Cyan
& $venvPy (Join-Path $PSScriptRoot "launcher.py")
