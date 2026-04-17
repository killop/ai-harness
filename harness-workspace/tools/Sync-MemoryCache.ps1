[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [string]$ProjectRoot = "",
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

if ([string]::IsNullOrWhiteSpace($KnowledgeCacheRoot)) {
    $KnowledgeCacheRoot = Join-Path $WorkspaceRoot "knowledges-cache"
}

$mapPath = Join-Path $PSScriptRoot "sync-map.json"
if (-not (Test-Path -LiteralPath $mapPath)) {
    throw "sync map not found: $mapPath"
}

$config = Get-Content -LiteralPath $mapPath -Raw | ConvertFrom-Json

$generatedRoots = @()
foreach ($mapping in $config.mappings) {
    $targetRoot = Join-Path $KnowledgeCacheRoot $mapping.target
    $generatedRoot = Split-Path -Parent $targetRoot
    if ($generatedRoots -notcontains $generatedRoot) {
        $generatedRoots += $generatedRoot
    }
}

foreach ($generatedRoot in $generatedRoots) {
    if (Test-Path -LiteralPath $generatedRoot) {
        Remove-Item -LiteralPath $generatedRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $generatedRoot -Force | Out-Null
}

function Test-PatternMatch {
    param(
        [string]$Value,
        [object[]]$Patterns
    )

    if (-not $Patterns -or $Patterns.Count -eq 0) {
        return $false
    }

    foreach ($pattern in $Patterns) {
        if ($Value -like [string]$pattern) {
            return $true
        }
    }

    return $false
}

foreach ($mapping in $config.mappings) {
    $sourceRoot = Join-Path $ProjectRoot $mapping.source
    $targetRoot = Join-Path $KnowledgeCacheRoot $mapping.target

    if (Test-Path -LiteralPath $targetRoot) {
        Remove-Item -LiteralPath $targetRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null

    if (-not (Test-Path -LiteralPath $sourceRoot)) {
        Write-Warning "skip missing source: $sourceRoot"
        continue
    }

    $resolvedSourceRoot = (Resolve-Path -LiteralPath $sourceRoot).Path.TrimEnd("\\")
    $copied = 0

    $sourceFiles = if ($mapping.recursive) {
        Get-ChildItem -LiteralPath $resolvedSourceRoot -Recurse -File
    } else {
        Get-ChildItem -LiteralPath $resolvedSourceRoot -File
    }

    foreach ($file in $sourceFiles) {
        $relativePath = $file.FullName.Substring($resolvedSourceRoot.Length).TrimStart("\\")

        if ($mapping.include.Count -gt 0) {
            $includeHit = (Test-PatternMatch -Value $file.Name -Patterns $mapping.include) -or
                (Test-PatternMatch -Value $relativePath -Patterns $mapping.include)
            if (-not $includeHit) {
                continue
            }
        }

        if (Test-PatternMatch -Value $relativePath -Patterns $mapping.exclude) {
            continue
        }

        $destination = Join-Path $targetRoot $relativePath
        $destinationDir = Split-Path -Parent $destination
        if (-not (Test-Path -LiteralPath $destinationDir)) {
            New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
        }

        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        $copied += 1
    }

    Write-Host ("[{0}] copied {1} file(s) -> {2}" -f $mapping.name, $copied, $mapping.target)
}

Write-Host ("Knowledge cache synchronized: {0}" -f $KnowledgeCacheRoot)
