# ============================================================
# FILE: Modules\AzureClient.ps1
# ============================================================

<#
.SYNOPSIS
    Azure CLI integration module
#>

class AzureClient {
    [string]$CurrentTenant
    [string]$CurrentSubscription
    [bool]$IsAvailable
    
    AzureClient() {
        $this.IsAvailable = $this.TestAzureCLI()
    }
    
    [bool] TestAzureCLI() {
        try {
            $null = az --version 2>$null
            return $?
        }
        catch {
            return $false
        }
    }
    
    [bool] TestLogin() {
        if (-not $this.IsAvailable) { return $false }
        
        try {
            $account = az account show 2>$null | ConvertFrom-Json
            if ($account) {
                $this.CurrentTenant = $account.tenantId
                $this.CurrentSubscription = $account.id
                return $true
            }
        }
        catch {}
        return $false
    }
    
    [hashtable] GetTenantInfo() {
        if (-not $this.TestLogin()) { return $null }
        
        try {
            $account = az account show | ConvertFrom-Json
            return @{
                TenantId = $account.tenantId
                SubscriptionId = $account.id
                SubscriptionName = $account.name
                DisplayName = $account.user.name
            }
        }
        catch {
            return $null
        }
    }
    
    [bool] Login([string]$TenantId) {
        try {
            if ($TenantId) {
                az login --tenant $TenantId
            }
            else {
                az login
            }
            return $?
        }
        catch {
            return $false
        }
    }
    
    [array] GetSubscriptions() {
        try {
            $subs = az account list | ConvertFrom-Json
            return $subs
        }
        catch {
            return @()
        }
    }
    
    [bool] SetSubscription([string]$SubscriptionId) {
        try {
            az account set --subscription $SubscriptionId
            return $?
        }
        catch {
            return $false
        }
    }
    
    [array] GetResourceGroups() {
        try {
            $groups = az group list | ConvertFrom-Json
            return $groups | Sort-Object name
        }
        catch {
            return @()
        }
    }
    
    [hashtable] ValidateTemplate([string]$ResourceGroup, [string]$TemplateFile, [string]$ParametersFile) {
        try {
            $cmd = "az deployment group validate --resource-group `"$ResourceGroup`" --template-file `"$TemplateFile`""
            if ($ParametersFile) {
                $cmd += " --parameters `"@$ParametersFile`""
            }
            
            $result = Invoke-Expression "$cmd 2>&1"
            
            if ($LASTEXITCODE -eq 0) {
                return @{ Success = $true; Message = "Validation successful" }
            }
            else {
                return @{ Success = $false; Message = ($result | Out-String) }
            }
        }
        catch {
            return @{ Success = $false; Message = $_.Exception.Message }
        }
    }
    
    [hashtable] DeployTemplate([string]$ResourceGroup, [string]$TemplateFile, [string]$ParametersFile, [string]$Mode) {
        try {
            $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
            $templateName = [System.IO.Path]::GetFileNameWithoutExtension($TemplateFile)
            $deploymentName = "$templateName-$timestamp"
            
            $cmd = "az deployment group create --resource-group `"$ResourceGroup`" --template-file `"$TemplateFile`" --name `"$deploymentName`" --mode $Mode"
            if ($ParametersFile) {
                $cmd += " --parameters `"@$ParametersFile`""
            }
            
            $result = Invoke-Expression "$cmd 2>&1"
            
            if ($LASTEXITCODE -eq 0) {
                return @{ Success = $true; Message = "Deployment successful (name: $deploymentName)" }
            }
            else {
                return @{ Success = $false; Message = ($result | Out-String) }
            }
        }
        catch {
            return @{ Success = $false; Message = $_.Exception.Message }
        }
    }
}