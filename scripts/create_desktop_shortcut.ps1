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
$Launcher = Join-Path $Root "launcher.py"
$VenvW = Join-Path $Root ".venv\Scripts\pythonw.exe"
$VenvC = Join-Path $Root ".venv\Scripts\python.exe"
$StartBat = Join-Path $Root "start.bat"

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 1
$Sc.Description = "Fajos Piteados Central - Centro de control (sin consola)"

# Preferir pythonw (sin consola) + launcher.py
if (Test-Path $VenvW) {
    $Sc.TargetPath = $VenvW
    $Sc.Arguments = "`"$Launcher`""
} elseif (Get-Command pyw -ErrorAction SilentlyContinue) {
    $Sc.TargetPath = (Get-Command pyw).Source
    $Sc.Arguments = "-3 `"$Launcher`""
} elseif (Get-Command pythonw -ErrorAction SilentlyContinue) {
    $Sc.TargetPath = (Get-Command pythonw).Source
    $Sc.Arguments = "`"$Launcher`""
} elseif (Test-Path $StartBat) {
    # Fallback: start.bat (silencioso si hay VBS)
    $Sc.TargetPath = $StartBat
    $Sc.Arguments = ""
} elseif (Test-Path $VenvC) {
    $Sc.TargetPath = $VenvC
    $Sc.Arguments = "`"$Launcher`""
} else {
    Write-Host "No hay Python. Ejecuta setup_windows.ps1" -ForegroundColor Red
    exit 1
}

if (Test-Path $Ico) {
    $Sc.IconLocation = "$Ico,0"
} else {
    Write-Host "AVISO: falta logo.ico" -ForegroundColor Yellow
}

$Sc.Save()
Write-Host "Acceso directo: $ShortcutPath" -ForegroundColor Green
Write-Host "  Destino: $($Sc.TargetPath) $($Sc.Arguments)"
Write-Host "  Icono: $(if (Test-Path $Ico) { $Ico } else { '(ninguno)' })"
