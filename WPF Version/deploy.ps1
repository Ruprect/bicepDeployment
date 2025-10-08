
# Main entry point - Deploy.ps1
#Requires -Version 5.1

<#
.SYNOPSIS
    Azure BICEP Deployment Tool with WPF GUI
.DESCRIPTION
    Main entry point for the modular deployment tool
.EXAMPLE
    .\Deploy.ps1
#>

# Add required assemblies first
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms

# Get script directory
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Import modules in correct order (dependencies first)
Write-Host "Loading modules..." -ForegroundColor Cyan

try {
    . "$ScriptPath\Modules\ConfigManager.ps1"
    Write-Host "  ✓ ConfigManager loaded" -ForegroundColor Green
    
    # Test that functions are available
    if (-not (Get-Command Load-DeploymentSettings -ErrorAction SilentlyContinue)) {
        throw "ConfigManager functions not loaded"
    }
}
catch {
    Write-Host "  ✗ ConfigManager failed: $_" -ForegroundColor Red
    exit 1
}

try {
    . "$ScriptPath\Modules\AzureClient.ps1"
    Write-Host "  ✓ AzureClient loaded" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ AzureClient failed: $_" -ForegroundColor Red
    exit 1
}

try {
    . "$ScriptPath\Modules\BicepManager.ps1"
    Write-Host "  ✓ BicepManager loaded" -ForegroundColor Green
    
    # Test that Get-BicepTemplates is available
    if (-not (Get-Command Get-BicepTemplates -ErrorAction SilentlyContinue)) {
        throw "Get-BicepTemplates function not found"
    }
    Write-Host "    → Get-BicepTemplates function confirmed" -ForegroundColor Gray
}
catch {
    Write-Host "  ✗ BicepManager failed: $_" -ForegroundColor Red
    Write-Host "    Error details: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "    At: $($_.InvocationInfo.PositionMessage)" -ForegroundColor Yellow
    exit 1
}

try {
    . "$ScriptPath\Modules\UI-ConfigDialog.ps1"
    Write-Host "  ✓ UI-ConfigDialog loaded" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ UI-ConfigDialog failed: $_" -ForegroundColor Red
    exit 1
}

try {
    . "$ScriptPath\Modules\UI-Dialogs.ps1"
    Write-Host "  ✓ UI-Dialogs loaded" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ UI-Dialogs failed: $_" -ForegroundColor Red
    exit 1
}

try {
    . "$ScriptPath\Modules\UI-MainWindow.ps1"
    Write-Host "  ✓ UI-MainWindow loaded" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ UI-MainWindow failed: $_" -ForegroundColor Red
    Write-Host "    Error details: $($_.Exception.Message)" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nAll modules loaded successfully!" -ForegroundColor Green
Write-Host "Starting application...`n" -ForegroundColor Cyan

# Initialize and show main window
try {
    Show-MainWindow
}
catch {
    Write-Host "Application error: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
    exit 1
}