#Requires -Version 7
<#
.SYNOPSIS
  Fajos Central — atajo para Windows / PowerShell 7
.DESCRIPTION
  Activa el venv si existe y abre el launcher GUI.
  Uso:  pwsh -File .\start.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$py = $null

if (Test-Path $venvPython) {
    $py = $venvPython
    Write-Host "Usando entorno virtual: .venv" -ForegroundColor Cyan
} else {
    $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
    if (-not $py) {
        $py = (Get-Command py -ErrorAction SilentlyContinue)?.Source
    }
}

if (-not $py) {
    Write-Host "No se encontró Python. Instálalo o crea el venv:" -ForegroundColor Red
    Write-Host "  py -3 -m venv .venv"
    Write-Host "  .\ .venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

Write-Host "Iniciando launcher..." -ForegroundColor Green
& $py (Join-Path $PSScriptRoot "launcher.py")
