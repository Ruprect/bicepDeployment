# bicepDeployment — Deployment Tool
#
# This script is part of the bicepDeployment tool itself.
# You should NOT run deployments from this folder.
#
# To set up a new consumer project, run:
#   .\init.ps1
#
# Then deploy from your consumer project folder using its deploy.ps1.

$isToolRoot = Test-Path (Join-Path $PSScriptRoot "deployScript/main.py")

if ($isToolRoot) {
    Write-Host ""
    Write-Host "  bicepDeployment — Tool Folder" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  You cannot run deployments from inside the bicepDeployment folder." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  To set up a new project, run:" -ForegroundColor White
    Write-Host "    .\init.ps1" -ForegroundColor Green
    Write-Host ""
    exit 0
}

Write-Host "deploy.ps1: unexpected execution context." -ForegroundColor Red
Write-Host "Run deploy.ps1 from your consumer project folder, not from bicepDeployment." -ForegroundColor Yellow
exit 1
