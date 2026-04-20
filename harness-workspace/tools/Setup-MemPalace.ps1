[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [string]$MempalaceRepo = "",
    [string]$VenvPath = "",
    [string]$PythonExe = "",
    [switch]$ForceRecreate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

if ([string]::IsNullOrWhiteSpace($MempalaceRepo)) {
    $MempalaceRepo = Join-Path $WorkspaceRoot "mempalace-github-code"
}

if ([string]::IsNullOrWhiteSpace($VenvPath)) {
    $VenvPath = Join-Path $MempalaceRepo ".venv"
}

if (-not (Test-Path -LiteralPath $MempalaceRepo)) {
    throw "MemPalace repo not found: $MempalaceRepo"
}

function Resolve-SetupPython {
    param([string]$RequestedPython)

    if (-not [string]::IsNullOrWhiteSpace($RequestedPython)) {
        if (Test-Path -LiteralPath $RequestedPython) {
            return (Resolve-Path -LiteralPath $RequestedPython).Path
        }

        $requestedCommand = Get-Command $RequestedPython -ErrorAction SilentlyContinue
        if ($null -ne $requestedCommand) {
            return $requestedCommand.Source
        }

        throw "Python executable not found: $RequestedPython"
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        $installedVersions = & $pyLauncher.Source -0p 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($version in @("3.11", "3.10", "3.9", "3.12", "3.13")) {
                $matchedLine = $installedVersions | Where-Object { $_ -match ("-V:{0}" -f [regex]::Escape($version)) } | Select-Object -First 1
                if (-not [string]::IsNullOrWhiteSpace($matchedLine)) {
                    $resolved = ($matchedLine -replace '^\s*-V:[^\s]+\s+\*?\s*', "").Trim()
                    if (-not [string]::IsNullOrWhiteSpace($resolved)) {
                        return $resolved
                    }
                }
            }
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        return $pythonCommand.Source
    }

    throw "No supported Python interpreter found. Install Python 3.9+ or pass -PythonExe."
}

$setupPython = Resolve-SetupPython -RequestedPython $PythonExe
$setupVersion = (& $setupPython -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not query Python version from $setupPython"
}

$versionParts = $setupVersion.Split(".")
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
    throw "Unsupported Python version $setupVersion at $setupPython. MemPalace requires Python 3.9+."
}

$venvPython = Join-Path $VenvPath "Scripts\python.exe"

if ($ForceRecreate -and (Test-Path -LiteralPath $VenvPath)) {
    Remove-Item -LiteralPath $VenvPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host ("Creating MemPalace venv with Python {0} at {1}" -f $setupVersion, $setupPython)
    & $setupPython -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create MemPalace venv: $VenvPath"
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "MemPalace venv python not found after creation: $venvPython"
}

Push-Location $MempalaceRepo
try {
    Write-Host ("Using venv python: {0}" -f $venvPython)

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in MemPalace venv"
    }

    & $venvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install MemPalace into the dedicated venv"
    }

    & $venvPython -c "import chromadb, yaml, mempalace.mcp_server; print('MemPalace setup ok')"
    if ($LASTEXITCODE -ne 0) {
        throw "MemPalace import verification failed"
    }
}
finally {
    Pop-Location
}

Write-Host "MemPalace setup complete."
Write-Host ("Repo: {0}" -f $MempalaceRepo)
Write-Host ("Venv: {0}" -f $VenvPath)
