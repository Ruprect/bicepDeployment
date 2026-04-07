param([switch]$LoadHelpersOnly)

. "$PSScriptRoot\_helpers.ps1"

#region Stub templates (written into consumer projects)

$script:StubDeploy = @'
# This project uses bicepDeployment for Azure Bicep deployments.
# See: https://github.com/Ruprect/bicepDeployment
$toolRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../bicepDeployment"))
if (Test-Path "$toolRoot/deploy.py") {
    python "$toolRoot/deploy.py"
} else {
    Write-Host "bicepDeployment not found at: $toolRoot" -ForegroundColor Red
    Write-Host "Run .\init.ps1 to re-initialize this project." -ForegroundColor Yellow
    exit 1
}
'@

$script:StubInit = @'
# Forwards to the bicepDeployment init script.
& "$PSScriptRoot/../bicepDeployment/init.ps1" @args
'@

$script:StubSetup = @'
# Forwards to the bicepDeployment setup script.
& "$PSScriptRoot/../bicepDeployment/setup.ps1" @args
'@

#endregion

if ($LoadHelpersOnly) { return }

#region Branch 2A -- Running inside bicepDeployment/ (create new consumer project)

function Invoke-Branch2A {
    Write-Host ""
    Write-Host "  bicepDeployment -- New Project Setup" -ForegroundColor Cyan
    Write-Host ""

    $projectName = Read-Host "  Enter new project name"
    if ([string]::IsNullOrWhiteSpace($projectName)) {
        Write-Host "  Project name cannot be empty." -ForegroundColor Red
        exit 1
    }

    $targetPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../$projectName"))

    # Already fully initialized check
    if ((Test-Path $targetPath) -and (Test-Path (Join-Path $targetPath "init.ps1"))) {
        Write-Host ""
        Write-Host "  '$projectName' is already initialized." -ForegroundColor Yellow
        Write-Host "  Path: $targetPath" -ForegroundColor Gray
        $ans = Read-Host "  Run setup.ps1 there instead? [Y/n]"
        if ($ans -ne 'n') { & (Join-Path $targetPath "setup.ps1") }
        return
    }

    # Create folder if needed
    if (-not (Test-Path $targetPath)) {
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        Write-Host "  Created: $targetPath" -ForegroundColor Green
    }

    # Compute relative path from consumer project to bicepDeployment tool
    $bicepRelPath = Get-RelativePath -From $targetPath -To $PSScriptRoot

    # Create or merge .code-workspace
    $workspaceFile = Join-Path $targetPath "$projectName.code-workspace"
    if (Test-Path $workspaceFile) {
        # Merge -- add reference if missing; never overwrite existing content
        $ws = Get-Content $workspaceFile -Raw | ConvertFrom-Json
        if (-not (Test-WorkspaceReferencesBicep -Workspace $ws -BicepRelPath $bicepRelPath)) {
            $folders = [System.Collections.Generic.List[object]]($ws.folders)
            $folders.Add([PSCustomObject]@{ path = $bicepRelPath })
            $ws | Add-Member -MemberType NoteProperty -Name folders -Value $folders.ToArray() -Force
            $ws | ConvertTo-Json -Depth 10 | Set-Content $workspaceFile
            Write-Host "  Patched workspace: added bicepDeployment reference" -ForegroundColor Green
        } else {
            Write-Host "  Workspace already references bicepDeployment." -ForegroundColor Gray
        }
    } else {
        [PSCustomObject]@{
            folders = @(
                [PSCustomObject]@{ path = "." },
                [PSCustomObject]@{ path = $bicepRelPath }
            )
        } | ConvertTo-Json -Depth 10 | Set-Content $workspaceFile
        Write-Host "  Created: $workspaceFile" -ForegroundColor Green
    }

    # Copy stubs -- only write if not already present
    $stubs = @{
        "deploy.ps1" = $script:StubDeploy
        "init.ps1"   = $script:StubInit
        "setup.ps1"  = $script:StubSetup
    }
    foreach ($stub in $stubs.GetEnumerator()) {
        $destFile = Join-Path $targetPath $stub.Key
        if (-not (Test-Path $destFile)) {
            Set-Content -Path $destFile -Value $stub.Value
            Write-Host "  Created stub: $($stub.Key)" -ForegroundColor Green
        }
    }

    # .gitignore offer
    Write-Host ""
    Write-Host "  parameters.*.json files contain secrets -- do not commit them." -ForegroundColor Yellow
    $ans = Read-Host "  Add 'parameters.*.json' to $projectName\.gitignore automatically? [Y/n]"
    if ($ans -ne 'n') {
        Add-GitIgnoreEntry -ProjectPath $targetPath -Entry "parameters.*.json"
    }

    Write-Host ""
    Write-Host "  Project '$projectName' is ready." -ForegroundColor Green
    Write-Host "  Next: run .\setup.ps1 in $projectName\ to configure deployment settings." -ForegroundColor White
    Write-Host ""

    # VS Code offer
    if (Get-Command code -ErrorAction SilentlyContinue) {
        $ans = Read-Host "  Open workspace in VS Code? [Y/n]"
        if ($ans -ne 'n') { code $workspaceFile }
    } else {
        Write-Host "  (VS Code not found on PATH - open $workspaceFile manually)" -ForegroundColor Gray
    }
}

#endregion

#region Branch 2B -- Running in a consumer project (patch workspace + run setup)

function Invoke-Branch2B {
    $consumerPath = $PSScriptRoot
    $toolPath     = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../bicepDeployment"))

    Write-Host ""
    Write-Host "  bicepDeployment -- Workspace Check" -ForegroundColor Cyan
    Write-Host ""

    if (-not (Test-Path $toolPath)) {
        Write-Host "  bicepDeployment not found at: $toolPath" -ForegroundColor Red
        Write-Host "  Ensure bicepDeployment is cloned relative to this project." -ForegroundColor Yellow
        exit 1
    }

    $bicepRelPath = Get-RelativePath -From $consumerPath -To $toolPath

    # Find all .code-workspace files in consumer project folder
    $workspaceFiles = @(Get-ChildItem -Path $consumerPath -Filter "*.code-workspace" -ErrorAction SilentlyContinue)

    if ($workspaceFiles.Count -eq 0) {
        Write-Host "  No .code-workspace file found in this folder." -ForegroundColor Yellow
        $ans = Read-Host "  Create one? [Y/n]"
        if ($ans -eq 'n') {
            Write-Host "  Skipped workspace creation." -ForegroundColor Gray
        } else {
            $folderName    = Split-Path $consumerPath -Leaf
            $workspaceFile = Join-Path $consumerPath "$folderName.code-workspace"
            [PSCustomObject]@{
                folders = @(
                    [PSCustomObject]@{ path = "." },
                    [PSCustomObject]@{ path = $bicepRelPath }
                )
            } | ConvertTo-Json -Depth 10 | Set-Content $workspaceFile
            Write-Host "  Created: $workspaceFile" -ForegroundColor Green
        }
    } else {
        # Select workspace file if multiple exist
        if ($workspaceFiles.Count -eq 1) {
            $workspaceFile = $workspaceFiles[0].FullName
        } else {
            Write-Host "  Multiple workspace files found:" -ForegroundColor Yellow
            for ($i = 0; $i -lt $workspaceFiles.Count; $i++) {
                Write-Host "  [$($i+1)] $($workspaceFiles[$i].Name)" -ForegroundColor White
            }
            $sel = Read-Host "  Select [1-$($workspaceFiles.Count)]"
            $workspaceFile = $workspaceFiles[[int]$sel - 1].FullName
        }

        $ws = Get-Content $workspaceFile -Raw | ConvertFrom-Json
        if (Test-WorkspaceReferencesBicep -Workspace $ws -BicepRelPath $bicepRelPath) {
            Write-Host "  Workspace already references bicepDeployment." -ForegroundColor Green
        } else {
            Write-Host "  bicepDeployment not referenced in workspace." -ForegroundColor Yellow
            $ans = Read-Host "  Add it? [Y/n]"
            if ($ans -ne 'n') {
                $folders = [System.Collections.Generic.List[object]]($ws.folders)
                $folders.Add([PSCustomObject]@{ path = $bicepRelPath })
                $ws | Add-Member -MemberType NoteProperty -Name folders -Value $folders.ToArray() -Force
                $ws | ConvertTo-Json -Depth 10 | Set-Content $workspaceFile
                Write-Host "  Workspace updated." -ForegroundColor Green
            }
        }
    }

    Write-Host ""
    $ans = Read-Host "  Run setup.ps1 to configure deployment settings? [Y/n]"
    if ($ans -ne 'n') {
        & (Join-Path $consumerPath "setup.ps1")
    }
}

#endregion

#region Entry point

if (Test-IsToolRoot) {
    Invoke-Branch2A
} else {
    Invoke-Branch2B
}

#endregion
