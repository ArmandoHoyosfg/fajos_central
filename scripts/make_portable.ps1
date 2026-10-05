#Requires -Version 7
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "launcher.py"))) {
    Write-Host "Ejecuta desde el repo fajos_central." -ForegroundColor Red
    exit 1
}

$Ver = "0.0.0"
$Vf = Join-Path $Root "VERSION"
if (Test-Path $Vf) { $Ver = (Get-Content $Vf -Raw).Trim() }

$Stamp = Get-Date -Format "yyyyMMdd"
$OutName = "FajosCentral_portable_v${Ver}_$Stamp"
$DestParent = Join-Path ([Environment]::GetFolderPath("Desktop")) $OutName
if (Test-Path $DestParent) { Remove-Item $DestParent -Recurse -Force }
New-Item -ItemType Directory -Path $DestParent | Out-Null

Write-Host "=== Empaque portable Fajos Central v$Ver ===" -ForegroundColor Cyan
Write-Host "Destino: $DestParent"

$ExcludeDirs = @(".venv", ".git", "__pycache__", ".pytest_cache", "exports", "backups", "logs", "node_modules", ".mypy_cache")

function Should-Skip([string]$rel) {
    foreach ($d in $ExcludeDirs) {
        if ($rel -eq $d -or $rel.StartsWith("$d\") -or $rel.Contains("\$d\")) { return $true }
    }
    if ($rel -eq "config.ini" -or $rel -eq ".env" -or $rel.EndsWith(".pyc")) { return $true }
    return $false
}

Get-ChildItem -Path $Root -Recurse -Force | ForEach-Object {
    $rel = $_.FullName.Substring($Root.Length).TrimStart("\")
    if ([string]::IsNullOrWhiteSpace($rel)) { return }
    if (Should-Skip $rel) { return }
    $target = Join-Path $DestParent $rel
    if ($_.PSIsContainer) {
        if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }
    } else {
        $parent = Split-Path $target -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item $_.FullName $target -Force
    }
}

$Ex = Join-Path $Root "config.ini.example"
if (Test-Path $Ex) { Copy-Item $Ex (Join-Path $DestParent "config.ini.example") -Force }

$leeme = @"
# Fajos Central portable v$Ver

## En otra PC Windows
1. Copia esta carpeta.
2. Instala Python 3.11+ (PATH + py launcher).
3. MariaDB + schema en HeidiSQL (db\schema).
4. pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
5. Copia config.ini.example -> config.ini y edita la BD.
6. pwsh -File .\scripts\create_desktop_shortcut.ps1
7. Doble clic en el acceso o: python .\launcher.py

No incluye .venv ni config.ini con contraseñas.
"@
Set-Content -Path (Join-Path $DestParent "LEEME_PORTABLE.md") -Value $leeme -Encoding UTF8

Write-Host "Listo: $DestParent" -ForegroundColor Green
