param(
    [switch]$SkipBuild,
    [switch]$Offline,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe. Create it first or adjust path."
}

if (-not $SkipBuild) {
    Write-Host "[1/2] Building project..." -ForegroundColor Cyan
    & $pythonExe "build.py"
}

if ($Offline) {
    $env:GROCERYGUARD_OFFLINE = "1"
    Write-Host "Offline mode enabled (GROCERYGUARD_OFFLINE=1)." -ForegroundColor Yellow
} else {
    Remove-Item Env:GROCERYGUARD_OFFLINE -ErrorAction SilentlyContinue
}

Write-Host "[2/2] Starting server on http://127.0.0.1:$Port ..." -ForegroundColor Green
& $pythonExe -m uvicorn src.groceryguard_core.guard_server:app --host 127.0.0.1 --port $Port
