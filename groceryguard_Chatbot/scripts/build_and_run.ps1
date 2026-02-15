param(
    [switch]$SkipBuild,
    [switch]$Offline,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

function Show-BuildErrorAndPause {
    param([string]$Message)
    Write-Host "" -ForegroundColor Red
    Write-Host "Build failed: $Message" -ForegroundColor Red
    Read-Host "Press Enter to close"
}

function Test-PortInUse {
    param([int]$CandidatePort)
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $CandidatePort -State Listen -ErrorAction SilentlyContinue
    return $null -ne $listener
}

function Get-FirstFreePort {
    param(
        [int]$StartPort,
        [int]$MaxAttempts = 25
    )

    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        $candidate = $StartPort + $i
        if (-not (Test-PortInUse -CandidatePort $candidate)) {
            return $candidate
        }
    }

    throw "No free localhost port found in range $StartPort-$($StartPort + $MaxAttempts - 1)."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe. Create it first or adjust path."
}

if (-not $SkipBuild) {
    Write-Host "[1/2] Building project..." -ForegroundColor Cyan
    & $pythonExe "build.py"
    if ($LASTEXITCODE -ne 0) {
        Show-BuildErrorAndPause -Message "build.py exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

if ($Offline) {
    $env:GROCERYGUARD_OFFLINE = "1"
    Write-Host "Offline mode enabled (GROCERYGUARD_OFFLINE=1)." -ForegroundColor Yellow
} else {
    Remove-Item Env:GROCERYGUARD_OFFLINE -ErrorAction SilentlyContinue
}

$selectedPort = $Port
if (Test-PortInUse -CandidatePort $selectedPort) {
    $fallbackPort = Get-FirstFreePort -StartPort ($selectedPort + 1)
    Write-Host "Port $selectedPort is already in use. Falling back to port $fallbackPort." -ForegroundColor Yellow
    $selectedPort = $fallbackPort
}

Write-Host "[2/2] Starting server on http://127.0.0.1:$selectedPort ..." -ForegroundColor Green
& $pythonExe -m uvicorn src.groceryguard_core.guard_server:app --host 127.0.0.1 --port $selectedPort
