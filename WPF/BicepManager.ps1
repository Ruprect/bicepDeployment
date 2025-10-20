# ============================================================
# FILE: Modules\BicepManager.ps1
# ============================================================

<#
.SYNOPSIS
    BICEP template management module
#>

class BicepTemplate {
    [string]$Name
    [string]$File
    [long]$Size
    [bool]$Enabled
    [datetime]$LastModified
    [nullable[bool]]$LastDeploymentSuccess
    [string]$LastDeploymentError
    [nullable[datetime]]$LastDeploymentTime
    [bool]$NeedsRedeployment
    [string]$LastFileHash
}

function Get-FileHash256 {
    param([string]$FilePath)
    
    try {
        $hash = Get-FileHash -Path $FilePath -Algorithm SHA256
        return $hash.Hash
    }
    catch {
        return $null
    }
}

function Get-BicepTemplates {
    $files = Get-ChildItem -Path "." -Filter "*.bicep" | Sort-Object Name
    $config = Load-DeploymentSettings
    $templates = [System.Collections.ArrayList]::new()
    
    foreach ($file in $files) {
        $fileSettings = $config.FileOrder | Where-Object { $_.FileName -eq $file.Name } | Select-Object -First 1
        
        $currentHash = Get-FileHash256 -FilePath $file.FullName
        $needsRedeployment = $false
        
        if ($fileSettings) {
            if ($fileSettings.LastDeploymentSuccess -eq $false) {
                $needsRedeployment = $true
            }
            elseif ($fileSettings.LastDeploymentSuccess -eq $true) {
                if ($currentHash -and $fileSettings.LastFileHash -and $currentHash -ne $fileSettings.LastFileHash) {
                    $needsRedeployment = $true
                }
            }
        }
        else {
            $needsRedeployment = $true
        }
        
        $isEnabled = if ($file.Length -eq 0) { $false } else { if ($fileSettings) { $fileSettings.Enabled } else { $false } }
        
        $template = [BicepTemplate]::new()
        $template.Name = $file.Name
        $template.File = $file.FullName
        $template.Size = $file.Length
        $template.Enabled = $isEnabled
        $template.LastModified = $file.LastWriteTime
        $template.NeedsRedeployment = $needsRedeployment
        $template.LastFileHash = $currentHash
        
        if ($fileSettings) {
            $template.LastDeploymentSuccess = $fileSettings.LastDeploymentSuccess
            $template.LastDeploymentError = $fileSettings.LastDeploymentError
            if ($fileSettings.LastDeployment) {
                try {
                    $template.LastDeploymentTime = [datetime]::ParseExact($fileSettings.LastDeployment, "yyyy-MM-dd HH:mm:ss", $null)
                }
                catch {}
            }
        }
        
        [void]$templates.Add($template)
    }
    
    # Sort by order in config
    $sortedTemplates = [System.Collections.ArrayList]::new()
    foreach ($entry in $config.FileOrder) {
        $template = $templates | Where-Object { $_.Name -eq $entry.FileName } | Select-Object -First 1
        if ($template) {
            [void]$sortedTemplates.Add($template)
        }
    }
    
    # Add any templates not in config
    foreach ($template in $templates) {
        if ($sortedTemplates.Name -notcontains $template.Name) {
            [void]$sortedTemplates.Add($template)
        }
    }
    
    return $sortedTemplates
}

function Update-DeploymentHistory {
    param(
        [string]$TemplateName,
        [bool]$Success,
        [string]$ErrorMessage = $null
    )
    
    $config = Load-DeploymentSettings
    $fileEntry = $config.FileOrder | Where-Object { $_.FileName -eq $TemplateName } | Select-Object -First 1
    
    if (-not $fileEntry) {
        $fileEntry = @{ FileName = $TemplateName; Enabled = $true }
        [void]$config.FileOrder.Add($fileEntry)
    }
    
    $hash = Get-FileHash256 -FilePath $TemplateName
    $fileEntry.LastDeploymentSuccess = $Success
    $fileEntry.LastDeployment = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $fileEntry.LastFileHash = $hash
    
    if ($ErrorMessage) {
        $fileEntry.LastDeploymentError = $ErrorMessage
    }
    elseif ($fileEntry.PSObject.Properties.Name -contains 'LastDeploymentError') {
        $fileEntry.PSObject.Properties.Remove('LastDeploymentError')
    }
    
    Save-DeploymentSettings $config
}

function Save-TemplateOrder {
    param([array]$Templates)
    
    $config = Load-DeploymentSettings
    $config.FileOrder.Clear()
    
    foreach ($template in $Templates) {
        $existing = $config.FileOrder | Where-Object { $_.FileName -eq $template.Name }
        if ($existing) {
            [void]$config.FileOrder.Add($existing)
        }
        else {
            [void]$config.FileOrder.Add(@{
                FileName = $template.Name
                Enabled = $template.Enabled
            })
        }
    }
    
    Save-DeploymentSettings $config
}
