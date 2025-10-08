# ============================================================
# FILE: Modules\ConfigManager.ps1
# ============================================================

<#
.SYNOPSIS
    Configuration management module
#>

class DeploymentConfig {
    [string]$SelectedParameterFile
    [string]$LastUpdated
    [System.Collections.ArrayList]$FileOrder
    [hashtable]$Configuration

    DeploymentConfig() {
        $this.FileOrder = [System.Collections.ArrayList]::new()
        $this.Configuration = @{}
    }
}

$script:ConfigFile = ".deployment-settings.json"

function Load-DeploymentSettings {
    if (Test-Path $script:ConfigFile) {
        try {
            $json = Get-Content $script:ConfigFile -Raw | ConvertFrom-Json
            $config = [DeploymentConfig]::new()
            $config.SelectedParameterFile = $json.SelectedParameterFile
            $config.LastUpdated = $json.LastUpdated
            $config.FileOrder = [System.Collections.ArrayList]::new()
            
            if ($json.FileOrder) {
                $json.FileOrder | ForEach-Object {
                    [void]$config.FileOrder.Add($_)
                }
            }
            
            $config.Configuration = @{}
            if ($json.Configuration) {
                $json.Configuration.PSObject.Properties | ForEach-Object {
                    $config.Configuration[$_.Name] = $_.Value
                }
            }
            
            return $config
        }
        catch {
            Write-Warning "Failed to load settings: $_"
        }
    }
    return [DeploymentConfig]::new()
}

function Save-DeploymentSettings {
    param([DeploymentConfig]$Config)
    
    $Config.LastUpdated = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    $json = @{
        SelectedParameterFile = $Config.SelectedParameterFile
        LastUpdated = $Config.LastUpdated
        FileOrder = $Config.FileOrder
        Configuration = $Config.Configuration
    } | ConvertTo-Json -Depth 10
    
    $json | Set-Content $script:ConfigFile -Encoding UTF8
}

function Get-ConfigValue {
    param([string]$Key, $Default = $null)
    $config = Load-DeploymentSettings
    if ($config.Configuration.ContainsKey($Key)) {
        return $config.Configuration[$Key]
    }
    return $Default
}

function Set-ConfigValue {
    param([string]$Key, $Value)
    $config = Load-DeploymentSettings
    $config.Configuration[$Key] = $Value
    Save-DeploymentSettings $config
}