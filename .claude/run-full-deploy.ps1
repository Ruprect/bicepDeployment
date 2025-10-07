# Automated deployment script that runs all templates
param(
    [string]$ResourceGroup = "TestBicepDeploy"
)

# Navigate to the script directory
Set-Location $PSScriptRoot

Write-Host "Starting automated deployment..." -ForegroundColor Green

# Simulate user inputs for the deploy.ps1 script
# A = Deploy All Templates
# 1 = Incremental mode
# Y = Yes to continue

$inputs = @("A", "1", "")

$inputIndex = 0
$process = Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy", "Bypass", "-File", ".\deploy.ps1" -PassThru -NoNewWindow

# Wait for the process to complete
$process.WaitForExit()

Write-Host "Deployment process completed. Checking for log files..." -ForegroundColor Yellow

# List generated log files
$logFiles = Get-ChildItem -Path . -Filter "deployment-*.log" | Sort-Object LastWriteTime -Descending

if ($logFiles) {
    Write-Host "Log files created:" -ForegroundColor Green
    foreach ($log in $logFiles) {
        Write-Host "  - $($log.Name)" -ForegroundColor Yellow
    }
    
    $latestLog = $logFiles[0]
    Write-Host "`nLatest log file: $($latestLog.Name)" -ForegroundColor Green
    Write-Host "Log file size: $([math]::Round($latestLog.Length / 1KB, 2)) KB" -ForegroundColor Gray
} else {
    Write-Host "No log files found." -ForegroundColor Red
}