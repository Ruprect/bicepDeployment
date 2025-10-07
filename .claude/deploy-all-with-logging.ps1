# Full deployment script with logging
param(
    [string]$ResourceGroup = "TestBicepDeploy"
)

$LogFile = "deployment-$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
$LatestLogFile = "deployment-latest.log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    Write-Host $Message
    Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
    Add-Content -Path $LatestLogFile -Value $logEntry -Encoding UTF8
}

# Initialize log
$logHeader = @"
=== BICEP DEPLOYMENT LOG ===
Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Resource Group: $ResourceGroup
Script: Automated Full Deployment
============================

"@

$logHeader | Set-Content -Path $LogFile -Encoding UTF8
$logHeader | Set-Content -Path $LatestLogFile -Encoding UTF8

Write-Log "Starting automated full deployment" "START"

# Get all bicep files in deployment order
$templates = @(
    @{Name="00.0.connections"; File="00.0.connections.bicep"; Description="API Connections"},
    @{Name="00.1.StorageAccount"; File="00.1.StorageAccount.bicep"; Description="Storage Account with Blob Connection"},
    @{Name="01.1.Helper.GetErrorMessage"; File="01.1.Helper.GetErrorMessage.bicep"; Description="Helper - Get Error Message"},
    @{Name="01.2.Helper.SendNotification"; File="01.2.Helper.SendNotification.bicep"; Description="Helper - Send Notification"},
    @{Name="01.3.Helper.ThrowError"; File="01.3.Helper.ThrowError.bicep"; Description="Helper - Throw Error"},
    @{Name="03.0-AccellaHandler"; File="03.0-AccellaHandler.bicep"; Description="Accella Handler Logic App"},
    @{Name="03.1-AccellaHandler_byCountry"; File="03.1-AccellaHandler_byCountry.bicep"; Description="Accella Handler by Country"},
    @{Name="11.0-BCDataHandler"; File="11.0-BCDataHandler.bicep"; Description="Business Central Data Handler"},
    @{Name="11.1-Customers_byCountry"; File="11.1-Customers_byCountry.bicep"; Description="Customers by Country"},
    @{Name="11.2-ConfigurationTemplates_byCountry"; File="11.2-ConfigurationTemplates_byCountry.bicep"; Description="Configuration Templates by Country"},
    @{Name="11.3-Tank_byCountry"; File="11.3-Tank_byCountry.bicep"; Description="Tanks by Country"},
    @{Name="11.4-TankRentAgreement_byCountry"; File="11.4-TankRentAgreement_byCountry.bicep"; Description="Tank Rent Agreements by Country"},
    @{Name="11.5-FrameAgreement_byCountry"; File="11.5-FrameAgreement_byCountry.bicep"; Description="Frame Agreements by Country"},
    @{Name="11.7-SalesPeople_byCountry"; File="11.7-SalesPeople_byCountry.bicep"; Description="Sales People by Country"},
    @{Name="11.8-NaceCodes_byCountry"; File="11.8-NaceCodes_byCountry.bicep"; Description="NACE Codes by Country"}
)

Write-Log "Found $($templates.Count) templates to deploy" "INFO"

# Check Azure CLI
try {
    az --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI not found"
    }
    Write-Log "Azure CLI validation successful" "INFO"
} catch {
    Write-Log "ERROR: Azure CLI is not available" "ERROR"
    exit 1
}

$successCount = 0
$failedTemplates = @()
$deploymentStartTime = Get-Date

foreach ($template in $templates) {
    if (-not (Test-Path $template.File)) {
        Write-Log "SKIP: Template file not found: $($template.File)" "SKIP"
        continue
    }
    
    $templateStartTime = Get-Date
    Write-Log "=== Deploying: $($template.Name) ===" "DEPLOY"
    Write-Log "File: $($template.File)" "INFO"
    Write-Log "Description: $($template.Description)" "INFO"
    
    try {
        $result = az deployment group create --resource-group $ResourceGroup --template-file $template.File --parameters "@parameters.local.json" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $templateEndTime = Get-Date
            $duration = ($templateEndTime - $templateStartTime).TotalSeconds
            Write-Log "✓ SUCCESS: $($template.Name) deployed successfully (Duration: $([math]::Round($duration, 2))s)" "SUCCESS"
            $successCount++
        } else {
            $templateEndTime = Get-Date
            $duration = ($templateEndTime - $templateStartTime).TotalSeconds
            Write-Log "✗ FAILED: $($template.Name) deployment failed (Duration: $([math]::Round($duration, 2))s)" "ERROR"
            Write-Log "Error details: $result" "ERROR"
            $failedTemplates += $template.Name
        }
    } catch {
        $templateEndTime = Get-Date
        $duration = ($templateEndTime - $templateStartTime).TotalSeconds
        Write-Log "✗ EXCEPTION: $($template.Name) - $($_.Exception.Message) (Duration: $([math]::Round($duration, 2))s)" "ERROR"
        $failedTemplates += $template.Name
    }
    
    Start-Sleep -Seconds 2
}

$deploymentEndTime = Get-Date
$totalDuration = ($deploymentEndTime - $deploymentStartTime).TotalSeconds

Write-Log "=== DEPLOYMENT SUMMARY ===" "SUMMARY"
Write-Log "Successfully deployed: $successCount/$($templates.Count) templates" "SUMMARY"
Write-Log "Total deployment duration: $([math]::Round($totalDuration, 2)) seconds" "SUMMARY"

if ($failedTemplates.Count -gt 0) {
    Write-Log "Failed templates: $($failedTemplates -join ', ')" "SUMMARY"
}

Write-Log "=== DEPLOYMENT COMPLETED ===" "END"

Write-Host "`nDeployment completed! Log files:" -ForegroundColor Green
Write-Host "  - $LogFile" -ForegroundColor Yellow
Write-Host "  - $LatestLogFile" -ForegroundColor Yellow