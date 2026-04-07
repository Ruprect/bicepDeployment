# _helpers.ps1 — Shared utilities for init.ps1 and setup.ps1
# Dot-source this file at the top of both scripts.

function Test-IsToolRoot {
    param([string]$Path = $PSScriptRoot)
    return Test-Path (Join-Path $Path "deployScript\main.py")
}

function Get-RelativePath {
    # PS 5.1 compatible — uses Uri.MakeRelativeUri (no .NET Core required)
    param([string]$From, [string]$To)
    $fromFull = [System.IO.Path]::GetFullPath($From).TrimEnd('\') + '\'
    $toFull   = [System.IO.Path]::GetFullPath($To)
    $fromUri  = [Uri]::new($fromFull)
    $toUri    = [Uri]::new($toFull)
    $rel      = $fromUri.MakeRelativeUri($toUri).ToString()
    # Uri uses forward slashes; convert to backslashes for Windows
    return [Uri]::UnescapeDataString($rel) -replace '/', '\'
}

function Test-WorkspaceReferencesBicep {
    param($Workspace, [string]$BicepRelPath)
    foreach ($folder in $Workspace.folders) {
        if ($folder.path -eq $BicepRelPath) { return $true }
    }
    return $false
}

function Add-GitIgnoreEntry {
    param([string]$ProjectPath, [string]$Entry)
    $gitignorePath = Join-Path $ProjectPath ".gitignore"
    if (Test-Path $gitignorePath) {
        $existing = Get-Content $gitignorePath -Raw
        if ($existing -match [regex]::Escape($Entry)) {
            Write-Host "  '$Entry' already in .gitignore" -ForegroundColor Gray
            return
        }
        Add-Content $gitignorePath "`n$Entry"
    } else {
        Set-Content $gitignorePath $Entry
    }
    Write-Host "  Added '$Entry' to .gitignore" -ForegroundColor Green
}
