[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [string]$ProjectRoot = "",
    [string]$PalacePath = "",
    [string]$MempalaceRepo = "",
    [string]$KnowledgeCacheRoot = "",
    [switch]$SkipSync
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $WorkspaceRoot "..")).Path
}

if ([string]::IsNullOrWhiteSpace($PalacePath)) {
    $PalacePath = Join-Path $WorkspaceRoot ".mempalace_local\\palace"
}

if ([string]::IsNullOrWhiteSpace($MempalaceRepo)) {
    $MempalaceRepo = Join-Path $WorkspaceRoot "mempalace-github-code"
}

if ([string]::IsNullOrWhiteSpace($KnowledgeCacheRoot)) {
    $KnowledgeCacheRoot = Join-Path $WorkspaceRoot "knowledges-cache"
}

if (-not (Test-Path -LiteralPath $MempalaceRepo)) {
    throw "MemPalace repo not found: $MempalaceRepo"
}

$pythonExe = Join-Path $MempalaceRepo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $setupScript = Join-Path $PSScriptRoot "Setup-MemPalace.ps1"
    throw "MemPalace venv not found: $pythonExe`nRun: powershell -ExecutionPolicy Bypass -File `"$setupScript`""
}

if (-not $SkipSync) {
    & (Join-Path $PSScriptRoot "Sync-MemoryCache.ps1") `
        -WorkspaceRoot $WorkspaceRoot `
        -ProjectRoot $ProjectRoot `
        -KnowledgeCacheRoot $KnowledgeCacheRoot
}

New-Item -ItemType Directory -Path $PalacePath -Force | Out-Null

$wingDirs = Get-ChildItem -LiteralPath $KnowledgeCacheRoot -Directory | Where-Object {
    Test-Path -LiteralPath (Join-Path $_.FullName "mempalace.yaml")
}

try {
    Push-Location $MempalaceRepo
    foreach ($wingDir in $wingDirs) {
        Write-Host ("Mining {0} -> {1}" -f $wingDir.FullName, $PalacePath)
        & $pythonExe -m mempalace.cli --palace $PalacePath mine $wingDir.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "MemPalace mine failed for $($wingDir.FullName)"
        }
    }
}
finally {
    Pop-Location
}

Write-Host "MemPalace refresh complete."
Write-Host ("Palace path: {0}" -f $PalacePath)
Write-Host ("Knowledge cache: {0}" -f $KnowledgeCacheRoot)
