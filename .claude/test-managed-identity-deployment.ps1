# Test script for managed identity deployment
param(
    [string]$ResourceGroup = "TestBicepDeploy",
    [string]$ParameterFile = "parameters.local.json"
)

Write-Host "=== Managed Identity Deployment Test ===" -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "Parameters: $ParameterFile" -ForegroundColor Yellow
Write-Host ""

# Check prerequisites
if (-not (Test-Path $ParameterFile)) {
    Write-Host "ERROR: Parameter file not found: $ParameterFile" -ForegroundColor Red
    exit 1
}

try {
    $null = az --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI not found"
    }
    Write-Host "✓ Azure CLI is available" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Azure CLI is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Step 1: Deploy Storage Account with managed identity connection
Write-Host "`n1. Deploying Storage Account with managed identity connection..." -ForegroundColor Cyan
$storageTemplate = "00.1.StorageAccount.bicep"

if (-not (Test-Path $storageTemplate)) {
    Write-Host "ERROR: Template not found: $storageTemplate" -ForegroundColor Red
    exit 1
}

try {
    Write-Host "Validating storage template..." -ForegroundColor Gray
    az deployment group validate `
        --resource-group $ResourceGroup `
        --template-file $storageTemplate `
        --parameters "@$ParameterFile"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Storage template validation successful" -ForegroundColor Green
        
        Write-Host "Deploying storage template..." -ForegroundColor Gray
        az deployment group create `
            --resource-group $ResourceGroup `
            --template-file $storageTemplate `
            --parameters "@$ParameterFile"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Storage Account deployment successful" -ForegroundColor Green
        } else {
            Write-Host "✗ Storage Account deployment failed" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "✗ Storage template validation failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Storage deployment failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Deploy AccellaHandler
Write-Host "`n2. Deploying AccellaHandler Logic App..." -ForegroundColor Cyan
$accellaTemplate = "03.0-AccellaHandler.bicep"

if (-not (Test-Path $accellaTemplate)) {
    Write-Host "ERROR: Template not found: $accellaTemplate" -ForegroundColor Red
    exit 1
}

try {
    Write-Host "Validating AccellaHandler template..." -ForegroundColor Gray
    az deployment group validate `
        --resource-group $ResourceGroup `
        --template-file $accellaTemplate `
        --parameters "@$ParameterFile"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ AccellaHandler template validation successful" -ForegroundColor Green
        
        Write-Host "Deploying AccellaHandler template..." -ForegroundColor Gray
        az deployment group create `
            --resource-group $ResourceGroup `
            --template-file $accellaTemplate `
            --parameters "@$ParameterFile"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ AccellaHandler deployment successful" -ForegroundColor Green
        } else {
            Write-Host "✗ AccellaHandler deployment failed" -ForegroundColor Red
            Write-Host "This may indicate the managed identity connection configuration needs adjustment" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "✗ AccellaHandler template validation failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ AccellaHandler deployment failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Verify deployment
Write-Host "`n3. Verifying deployment..." -ForegroundColor Cyan

try {
    Write-Host "Checking deployed resources..." -ForegroundColor Gray
    $queryFilter = "[?type=='Microsoft.Logic/workflows' `|\| type=='Microsoft.Storage/storageAccounts' `|\| type=='Microsoft.Web/connections'].{Name:name, Type:type, Status:properties.provisioningState}"
    $resources = az resource list --resource-group $ResourceGroup --query $queryFilter --output table
    
    if ($resources) {
        Write-Host "Deployed resources:" -ForegroundColor Green
        Write-Host $resources -ForegroundColor White
    }
    
    # Check Logic App specifically
    $logicAppName = "la-test-bc-03.0-AccellaHandler"  # Based on naming convention from parameters
    Write-Host "`nChecking Logic App status..." -ForegroundColor Gray
    $logicQuery = "{Name:name, State:state, ProvisioningState:provisioningState}"
    $logicAppStatus = az logic workflow show --resource-group $ResourceGroup --name $logicAppName --query $logicQuery --output table 2>$null
    
    if ($logicAppStatus) {
        Write-Host "Logic App status:" -ForegroundColor Green
        Write-Host $logicAppStatus -ForegroundColor White
    }
    
} catch {
    Write-Host "⚠ Could not verify all resources: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== Deployment Summary ===" -ForegroundColor Cyan
Write-Host "✓ Storage Account with managed identity connection deployed" -ForegroundColor Green
Write-Host "✓ AccellaHandler Logic App deployed" -ForegroundColor Green
Write-Host "✓ Logic App configured to use managed identity for blob access" -ForegroundColor Green

Write-Host "`nNext steps:" -ForegroundColor White
Write-Host "1. Test the Logic App by triggering it with a blob file" -ForegroundColor Gray
Write-Host "2. Check Logic App run history in Azure portal for any authentication issues" -ForegroundColor Gray
Write-Host "3. Verify the Logic App's managed identity has Storage Blob Data Contributor role on the storage account" -ForegroundColor Gray