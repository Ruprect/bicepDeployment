# Test script for StorageAccount.bicep template validation
param(
    [string]$ResourceGroup = "TestBicepDeploy",
    [string]$TemplateFile = "00.1.StorageAccount.bicep",
    [string]$ParameterFile = "parameters.local.json"
)

Write-Host "=== Bicep Template Validation Test ===" -ForegroundColor Cyan
Write-Host "Template: $TemplateFile" -ForegroundColor Yellow
Write-Host "Parameters: $ParameterFile" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host ""

# Check if files exist
if (-not (Test-Path $TemplateFile)) {
    Write-Host "ERROR: Template file not found: $TemplateFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ParameterFile)) {
    Write-Host "ERROR: Parameter file not found: $ParameterFile" -ForegroundColor Red
    exit 1
}

# Check if Azure CLI is available
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

# Step 1: Bicep build test
Write-Host "`n1. Testing Bicep build..." -ForegroundColor Cyan
try {
    az bicep build --file $TemplateFile
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Bicep build successful" -ForegroundColor Green
    } else {
        Write-Host "✗ Bicep build failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Bicep build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Template validation
Write-Host "`n2. Validating template deployment..." -ForegroundColor Cyan
try {
    az deployment group validate `
        --resource-group $ResourceGroup `
        --template-file $TemplateFile `
        --parameters "@$ParameterFile"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Template validation successful" -ForegroundColor Green
    } else {
        Write-Host "✗ Template validation failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Template validation failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: What-if analysis (optional)
Write-Host "`n3. Running what-if analysis..." -ForegroundColor Cyan
try {
    az deployment group what-if `
        --resource-group $ResourceGroup `
        --template-file $TemplateFile `
        --parameters "@$ParameterFile"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ What-if analysis completed" -ForegroundColor Green
    } else {
        Write-Host "⚠ What-if analysis had warnings (this may be normal)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ What-if analysis failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
Write-Host "✓ Bicep syntax is valid" -ForegroundColor Green
Write-Host "✓ Template parameters are correct" -ForegroundColor Green
Write-Host "✓ Azure resource definitions are valid" -ForegroundColor Green
Write-Host "✓ Template is ready for deployment" -ForegroundColor Green

Write-Host "`nTo deploy the template, run:" -ForegroundColor White
Write-Host "az deployment group create --resource-group $ResourceGroup --template-file $TemplateFile --parameters `"@$ParameterFile`"" -ForegroundColor Gray