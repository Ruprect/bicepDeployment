param([switch]$LoadHelpersOnly)

. "$PSScriptRoot\_helpers.ps1"

#region Helpers

function Read-WithDefault {
    param([string]$Prompt, [string]$Default = "")
    $display = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
    $value = Read-Host "  $display"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function Read-Required {
    param([string]$Prompt)
    do {
        $value = Read-Host "  $Prompt"
        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Host "  This field is required." -ForegroundColor Red
        }
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value
}

function Get-DeploymentSettings {
    param([string]$Path = (Join-Path $PWD ".deployment-settings.json"))
    $defaults = @{
        SelectedParameterFile = $null
        FileOrder             = @()
        Configuration         = @{
            ResourceGroup  = ""
            Subscription   = ""
            DesiredTenant  = ""
            ConsoleWidth   = 75
            ValidationMode = "All"
        }
    }
    if (-not (Test-Path $Path)) { return $defaults }
    try {
        $loaded = Get-Content $Path -Raw | ConvertFrom-Json
        if ($null -ne $loaded.FileOrder)             { $defaults.FileOrder = $loaded.FileOrder }
        if ($null -ne $loaded.SelectedParameterFile) { $defaults.SelectedParameterFile = $loaded.SelectedParameterFile }
        if ($null -ne $loaded.Configuration) {
            foreach ($key in $loaded.Configuration.PSObject.Properties.Name) {
                $defaults.Configuration[$key] = $loaded.Configuration.$key
            }
        }
        return $defaults
    } catch {
        Write-Host "  Warning: could not parse existing settings. Starting fresh." -ForegroundColor Yellow
        return $defaults
    }
}

function Get-PlaceholderFields {
    param($Obj, [string]$Path)
    $results = @()
    if ($null -eq $Obj) { return $results }
    if ($Obj -is [string]) {
        if ($Obj -eq "<PLACEHOLDER>") { $results += $Path }
        return $results
    }
    if ($Obj -is [System.Management.Automation.PSCustomObject]) {
        foreach ($prop in $Obj.PSObject.Properties) {
            $childPath = if ($Path) { "$Path.$($prop.Name)" } else { $prop.Name }
            $results += Get-PlaceholderFields -Obj $prop.Value -Path $childPath
        }
    }
    return $results
}

#endregion

if ($LoadHelpersOnly) { return }

#region Mode 1 -- Deployment settings (.deployment-settings.json)

function Invoke-Mode1 {
    Write-Host ""
    Write-Host "  Deployment Settings (.deployment-settings.json)" -ForegroundColor Cyan
    Write-Host ""

    $settingsPath = Join-Path $PWD ".deployment-settings.json"
    $settings     = Get-DeploymentSettings -Path $settingsPath
    $cfg          = $settings.Configuration

    $rg  = if ($cfg.ResourceGroup)  { " [$($cfg.ResourceGroup)]" }  else { " (required)" }
    $sub = if ($cfg.Subscription)   { " [$($cfg.Subscription)]" }   else { " (required)" }
    $ten = if ($cfg.DesiredTenant)  { " [$($cfg.DesiredTenant)]" }  else { " (required)" }

    $cfg.ResourceGroup = Read-Required -Prompt "Resource group name$rg"
    $cfg.Subscription  = Read-Required -Prompt "Subscription ID$sub"
    $cfg.DesiredTenant = Read-Required -Prompt "Tenant ID$ten"

    Write-Host ""
    Write-Host "  Validation mode:" -ForegroundColor White
    Write-Host "  [1] All      -- validate before every deployment" -ForegroundColor Gray
    Write-Host "  [2] Changed  -- only validate changed files"       -ForegroundColor Gray
    Write-Host "  [3] Skip     -- no validation"                     -ForegroundColor Gray
    $modes   = @("All", "Changed", "Skip")
    $currIdx = ([array]::IndexOf($modes, $cfg.ValidationMode) + 1).ToString()
    $sel     = Read-WithDefault -Prompt "Select [1-3]" -Default $currIdx
    $cfg.ValidationMode = $modes[[int]$sel - 1]

    $cfg.ConsoleWidth = [int](Read-WithDefault -Prompt "Console width" -Default "$($cfg.ConsoleWidth)")

    $output = [PSCustomObject]@{
        SelectedParameterFile = $settings.SelectedParameterFile
        LastUpdated           = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        FileOrder             = $settings.FileOrder
        Configuration         = $cfg
    }

    $output | ConvertTo-Json -Depth 10 | Set-Content $settingsPath
    Write-Host ""
    Write-Host "  Saved: $settingsPath" -ForegroundColor Green
    Write-Host ""
}

#endregion

#region Mode 2 -- stub (implemented in Task 7)

function Invoke-Mode2 {
    Write-Host "  Mode 2 not yet implemented." -ForegroundColor Yellow
}

#endregion

#region Entry point

Write-Host ""
Write-Host "  bicepDeployment Setup" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [1] Deployment settings (.deployment-settings.json)" -ForegroundColor White
Write-Host "  [2] Parameters file (parameters.{env}.json)"         -ForegroundColor White
Write-Host ""
$choice = Read-Host "  Select [1-2]"

switch ($choice) {
    "1" { Invoke-Mode1 }
    "2" { Invoke-Mode2 }
    default { Write-Host "  Invalid selection." -ForegroundColor Red; exit 1 }
}

#endregion
