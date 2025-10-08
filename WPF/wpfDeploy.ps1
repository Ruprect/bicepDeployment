# Main entry point - Deploy.ps1
#Requires -Version 5.1

<#
.SYNOPSIS
    Azure BICEP Deployment Tool with WPF GUI
.DESCRIPTION
    Main entry point for the modular deployment tool
#>

# Import modules
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$ScriptPath\Modules\ConfigManager.ps1"
. "$ScriptPath\Modules\AzureClient.ps1"
. "$ScriptPath\Modules\BicepManager.ps1"
. "$ScriptPath\Modules\UI-MainWindow.ps1"
. "$ScriptPath\Modules\UI-ConfigDialog.ps1"
. "$ScriptPath\Modules\UI-Dialogs.ps1"

# Add required assemblies
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms

# Initialize and show main window
Show-MainWindow