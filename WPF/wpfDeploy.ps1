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
. "$ScriptPath\ConfigManager.ps1"
. "$ScriptPath\AzureClient.ps1"
. "$ScriptPath\BicepManager.ps1"
. "$ScriptPath\UI-MainWindow.ps1"
. "$ScriptPath\UI-ConfigDialog.ps1"
. "$ScriptPath\UI-Dialogs.ps1"

# Add required assemblies
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms

# Initialize and show main window
Show-MainWindow