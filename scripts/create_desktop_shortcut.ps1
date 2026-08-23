#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "launcher.py"))) {
    $Root = $PSScriptRoot
}
if (-not (Test-Path (Join-Path $Root "launcher.py"))) {
    Write-Host "No se encontro launcher.py" -ForegroundColor Red
    exit 1
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Fajos Central.lnk"
$Ico = Join-Path $Root "app\web\static\logo.ico"
$StartBat = Join-Path $Root "start.bat"

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = "Fajos Piteados Central - Launcher"

# Preferir start.bat (integrado: venv, icono, doble clic)
if (Test-Path $StartBat) {
    $Sc.TargetPath = $StartBat
    $Sc.Arguments = ""
} else {
    $VenvPy = Join-Path $Root ".venv\Scripts\pythonw.exe"
    $VenvPyConsole = Join-Path $Root ".venv\Scripts\python.exe"
    $Launcher = Join-Path $Root "launcher.py"
    if (Test-Path $VenvPy) {
        $Sc.TargetPath = $VenvPy
        $Sc.Arguments = "`"$Launcher`""
    } elseif (Test-Path $VenvPyConsole) {
        $Sc.TargetPath = $VenvPyConsole
        $Sc.Arguments = "`"$Launcher`""
    } else {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            $Sc.TargetPath = $py.Source
            $Sc.Arguments = "-3 `"$Launcher`""
        } else {
            $python = Get-Command python -ErrorAction SilentlyContinue
            if (-not $python) {
                Write-Host "No hay Python ni .venv. Ejecuta setup_windows.ps1" -ForegroundColor Red
                exit 1
            }
            $Sc.TargetPath = $python.Source
            $Sc.Arguments = "`"$Launcher`""
        }
    }
}

if (Test-Path $Ico) {
    $Sc.IconLocation = "$Ico,0"
} else {
    Write-Host "AVISO: falta logo.ico" -ForegroundColor Yellow
}

$Sc.Save()
Write-Host "Acceso directo creado: $ShortcutPath" -ForegroundColor Green
Write-Host "  Destino: $($Sc.TargetPath) $($Sc.Arguments)"
Write-Host "  Icono: $(if (Test-Path $Ico) { $Ico } else { '(ninguno)' })"
