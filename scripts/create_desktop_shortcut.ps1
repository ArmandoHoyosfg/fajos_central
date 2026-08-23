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

$VenvPy = Join-Path $Root ".venv\Scripts\pythonw.exe"
$VenvPyConsole = Join-Path $Root ".venv\Scripts\python.exe"
$Target = $null
$Args = '"' + (Join-Path $Root "launcher.py") + '"'

if (Test-Path $VenvPy) {
    $Target = $VenvPy
} elseif (Test-Path $VenvPyConsole) {
    $Target = $VenvPyConsole
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $Target = $py.Source
        $Args = "-3 " + $Args
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if ($python) { $Target = $python.Source }
        else {
            Write-Host "No hay Python ni .venv. Ejecuta setup_windows.ps1" -ForegroundColor Red
            exit 1
        }
    }
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Target
$Sc.Arguments = $Args
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = "Fajos Piteados Central - Launcher"
$Ico = Join-Path $Root "app\web\static\logo.ico"
if (Test-Path $Ico) { $Sc.IconLocation = "$Ico,0" }
$Sc.Save()

Write-Host "Acceso directo creado: $ShortcutPath" -ForegroundColor Green
Write-Host "Destino: $Target $Args"
