#Requires -Version 7
<#
.SYNOPSIS
  Instalación / reparación del entorno en Windows (PowerShell 7)

.NOTES
  Si sale 'not digitally signed', ejecuta:
    pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
  O doble clic en setup_windows.cmd

.DESCRIPTION
  - Detecta un Python usable (py launcher preferido)
  - Recrea .venv si apunta a un intérprete inexistente (ej. Python314 borrado)
  - Instala requirements.txt con python -m pip (evita pip.exe roto)
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Fajos Central — Setup / reparación Windows ===" -ForegroundColor Cyan
Write-Host ""

function Find-Python {
    $candidates = @(
        @{ Args = @("-3.14"); Label = "py -3.14" },
        @{ Args = @("-3.13"); Label = "py -3.13" },
        @{ Args = @("-3.12"); Label = "py -3.12" },
        @{ Args = @("-3.11"); Label = "py -3.11" },
        @{ Args = @("-3");    Label = "py -3" }
    )
    foreach ($c in $candidates) {
        try {
            $ver = & py @($c.Args) -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver -and (Test-Path $ver.Trim())) {
                Write-Host "  Encontrado: $($c.Label) -> $($ver.Trim())" -ForegroundColor Green
                return @{ Exe = $ver.Trim(); PyArgs = $c.Args; Label = $c.Label }
            }
        } catch { }
    }
    try {
        $exe = & python -c "import sys; print(sys.executable)" 2>$null
        if ($exe -and (Test-Path $exe.Trim())) {
            $pathLower = $exe.Trim().ToLower()
            if ($pathLower -match "inkscape") {
                Write-Host "  AVISO: 'python' apunta a Inkscape: $exe" -ForegroundColor Yellow
                Write-Host "  No se usará. Instala Python desde python.org o usa el launcher 'py'." -ForegroundColor Yellow
            } else {
                Write-Host "  Encontrado: python -> $($exe.Trim())" -ForegroundColor Green
                return @{ Exe = $exe.Trim(); PyArgs = $null; Label = "python" }
            }
        }
    } catch { }
    return $null
}

Write-Host "1) Buscando Python..." -ForegroundColor Cyan
$py = Find-Python
if (-not $py) {
    Write-Host ""
    Write-Host "No se encontró un Python usable." -ForegroundColor Red
    Write-Host "Opciones:" -ForegroundColor Yellow
    Write-Host "  A) Instala/repara Python desde https://www.python.org/downloads/"
    Write-Host "     Marca: 'Add python.exe to PATH' y 'py launcher'"
    Write-Host "  B) Si ya está instalado, lista versiones:"
    Write-Host "       py --list"
    Write-Host "  C) Evita el Python de Inkscape en el PATH del usuario."
    exit 1
}

Write-Host ""
Write-Host "2) Revisando .venv ..." -ForegroundColor Cyan
$venvPython = ".\.venv\Scripts\python.exe"
$needRecreate = $false
if (-not (Test-Path ".\.venv")) {
    Write-Host "  No existe .venv -> se creará."
    $needRecreate = $true
} else {
    $cfg = ".\.venv\pyvenv.cfg"
    if (Test-Path $cfg) {
        $homeLine = Get-Content $cfg | Where-Object { $_ -match '^\s*home\s*=' } | Select-Object -First 1
        if ($homeLine) {
            $home = ($homeLine -split '=', 2)[1].Trim()
            $homePy = Join-Path $home "python.exe"
            if (-not (Test-Path $homePy)) {
                Write-Host "  .venv roto: home='$home' no existe." -ForegroundColor Yellow
                $needRecreate = $true
            }
        }
    }
    if (-not (Test-Path $venvPython)) {
        Write-Host "  Falta .venv\Scripts\python.exe" -ForegroundColor Yellow
        $needRecreate = $true
    } else {
        & $venvPython -c "print(1)" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  .venv\Scripts\python.exe no ejecuta (intérprete base ausente)." -ForegroundColor Yellow
            $needRecreate = $true
        }
    }
}

if ($needRecreate) {
    if (Test-Path ".\.venv") {
        Write-Host "  Eliminando .venv antiguo..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force ".\.venv"
    }
    Write-Host "  Creando .venv con $($py.Label) ..."
    if ($null -ne $py.PyArgs) {
        & py @($py.PyArgs) -m venv .venv
    } else {
        & $py.Exe -m venv .venv
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Host "Falló la creación del venv." -ForegroundColor Red
        exit 1
    }
    Write-Host "  .venv creado." -ForegroundColor Green
} else {
    Write-Host "  .venv parece válido." -ForegroundColor Green
}

Write-Host ""
Write-Host "3) Instalando dependencias (python -m pip) ..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit 1 }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falló pip install. Revisa el error arriba." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "4) Archivos de config ..." -ForegroundColor Cyan
if (-not (Test-Path ".\.env") -and (Test-Path ".\.env.example")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "  Creado .env (edita usuario/contraseña MariaDB)." -ForegroundColor Yellow
}
if (-not (Test-Path ".\config.ini") -and (Test-Path ".\config.ini.example")) {
    Write-Host "  Tip: copia config.ini.example a config.ini o usa el launcher → Configurar conexión."
}

Write-Host ""
Write-Host "=== Listo ===" -ForegroundColor Green
Write-Host "Activa y ejecuta SIEMPRE con el Python del venv:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python --version"
Write-Host "  python launcher.py"
Write-Host ""
Write-Host "Si Activate.ps1 falla por política:" -ForegroundColor Yellow
Write-Host "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
Write-Host ""
Write-Host "Sin activar (equivalente):" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe launcher.py"
Write-Host "  o:  pwsh -File .\start.ps1"
