param(
    [switch]$SkipBuild,
    [switch]$Offline,
    [int]$Port = 8001,
    [string]$PythonExe
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

function Resolve-PythonExecutable {
    param([string]$Root)

    $candidates = @()

    if ($env:VIRTUAL_ENV) {
        $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }

    $candidates += (Join-Path $Root ".venv\Scripts\python.exe")

    $parent = Split-Path -Parent $Root
    if ($parent) {
        $candidates += (Join-Path $parent ".venv\Scripts\python.exe")
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and $pythonCmd.Source) {
        return $pythonCmd.Source
    }

    throw "Python executable not found. Tried: $($candidates -join ', '), and 'python' on PATH."
}

function Get-DotEnvApiKey {
    param([string]$EnvPath)

    if (-not (Test-Path $EnvPath)) {
        return $null
    }

    foreach ($line in Get-Content $EnvPath) {
        if ($line -match '^\s*OPENAI_API_KEY\s*=\s*(.+)\s*$') {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }
    }

    return $null
}

function Set-DotEnvApiKey {
    param(
        [string]$EnvPath,
        [string]$ApiKey
    )

    $entry = "OPENAI_API_KEY=$ApiKey"

    if (Test-Path $EnvPath) {
        $lines = [System.Collections.Generic.List[string]]::new()
        $found = $false
        foreach ($line in Get-Content $EnvPath) {
            if ($line -match '^\s*OPENAI_API_KEY\s*=') {
                if (-not $found) {
                    $lines.Add($entry)
                    $found = $true
                }
                continue
            }
            $lines.Add($line)
        }

        if (-not $found) {
            if ($lines.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($lines[$lines.Count - 1])) {
                $lines.Add("")
            }
            $lines.Add($entry)
        }

        Set-Content -Path $EnvPath -Value $lines -Encoding utf8
        return
    }

    Set-Content -Path $EnvPath -Value $entry -Encoding utf8
}

function Read-SecretInput {
    param([string]$Prompt)

    $secureValue = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Ensure-OpenAIApiKey {
    param([string]$Root)

    if (-not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        return $true
    }

    $envFile = Join-Path $Root ".env"
    $existingKey = Get-DotEnvApiKey -EnvPath $envFile
    if ($existingKey) {
        $env:OPENAI_API_KEY = $existingKey
        return $true
    }

    Write-Host "OPENAI_API_KEY was not found in environment or .env." -ForegroundColor Yellow
    $enteredKey = Read-SecretInput -Prompt "Enter OPENAI_API_KEY (leave blank for offline mode)"

    if ([string]::IsNullOrWhiteSpace($enteredKey)) {
        return $false
    }

    $env:OPENAI_API_KEY = $enteredKey
    Set-DotEnvApiKey -EnvPath $envFile -ApiKey $enteredKey
    Write-Host "Saved OPENAI_API_KEY to .env for future runs." -ForegroundColor Green
    return $true
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if ($PythonExe) {
    if (-not (Test-Path $PythonExe)) {
        throw "Provided Python executable does not exist: $PythonExe"
    }
    $pythonExe = $PythonExe
} else {
    $pythonExe = Resolve-PythonExecutable -Root $projectRoot
}

$hasApiKey = $true
if (-not $Offline) {
    $hasApiKey = Ensure-OpenAIApiKey -Root $projectRoot
}

$offlineModeEnabled = $Offline -or (-not $hasApiKey)

if (-not $SkipBuild) {
    Write-Host "[1/2] Building project..." -ForegroundColor Cyan
    & $pythonExe "build.py"
    if ($LASTEXITCODE -ne 0) {
        Show-BuildErrorAndPause -Message "build.py exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

if ($offlineModeEnabled) {
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
