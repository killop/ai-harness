[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [string]$ProjectRoot = "",
    [string]$PalacePath = "",
    [string]$MempalaceRepo = "",
    [string]$KnowledgeCacheRoot = ""
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

if (Test-Path -LiteralPath $PalacePath) {
    Remove-Item -LiteralPath $PalacePath -Recurse -Force
}

& (Join-Path $PSScriptRoot "Refresh-MemPalace.ps1") `
    -WorkspaceRoot $WorkspaceRoot `
    -ProjectRoot $ProjectRoot `
    -PalacePath $PalacePath `
    -MempalaceRepo $MempalaceRepo `
    -KnowledgeCacheRoot $KnowledgeCacheRoot
