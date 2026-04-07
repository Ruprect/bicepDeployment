param(
    [switch]$LoadHelpersOnly,
    [string]$ProjectPath = $PWD
)

. "$PSScriptRoot\_helpers.ps1"

#region Helpers

function Read-WithDefault {
    param([string]$Prompt, [string]$Default = "")
    $display = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
    $value = Read-Host "  $display"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function Read-Required {
    param([string]$Prompt, [string]$Default = "")
    do {
        $display = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
        $value = Read-Host "  $display"
        if ([string]::IsNullOrWhiteSpace($value)) { $value = $Default }
        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Host "  This field is required." -ForegroundColor Red
        }
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value
}

function Get-DeploymentSettings {
    param([string]$Path = (Join-Path $PWD ".deployment-settings.json"))
    $defaults = @{
        SelectedParameterFile = $null
        FileOrder             = @()
        Configuration         = @{
            ResourceGroup  = ""
            Subscription   = ""
            DesiredTenant  = ""
            ConsoleWidth   = 75
            ValidationMode = "All"
        }
    }
    if (-not (Test-Path $Path)) { return $defaults }
    try {
        $loaded = Get-Content $Path -Raw | ConvertFrom-Json
        if ($null -ne $loaded.FileOrder)             { $defaults.FileOrder = $loaded.FileOrder }
        if ($null -ne $loaded.SelectedParameterFile) { $defaults.SelectedParameterFile = $loaded.SelectedParameterFile }
        if ($null -ne $loaded.Configuration) {
            foreach ($key in $loaded.Configuration.PSObject.Properties.Name) {
                $defaults.Configuration[$key] = $loaded.Configuration.$key
            }
        }
        return $defaults
    } catch {
        Write-Host "  Warning: could not parse existing settings. Starting fresh." -ForegroundColor Yellow
        return $defaults
    }
}

function Get-PlaceholderFields {
    param($Obj, [string]$Path)
    $results = @()
    if ($null -eq $Obj) { return $results }
    if ($Obj -is [string]) {
        if ($Obj -eq "<PLACEHOLDER>") { $results += $Path }
        return $results
    }
    if ($Obj -is [System.Management.Automation.PSCustomObject]) {
        foreach ($prop in $Obj.PSObject.Properties) {
            $childPath = if ($Path) { "$Path.$($prop.Name)" } else { $prop.Name }
            $results += Get-PlaceholderFields -Obj $prop.Value -Path $childPath
        }
    }
    return $results
}

#endregion

if ($LoadHelpersOnly) { return }

#region Mode 1 -- Deployment settings (.deployment-settings.json)

function Invoke-Mode1 {
    Write-Host ""
    Write-Host "  Deployment Settings (.deployment-settings.json)" -ForegroundColor Cyan
    Write-Host ""

    $settingsPath = Join-Path $ProjectPath ".deployment-settings.json"
    $settings     = Get-DeploymentSettings -Path $settingsPath
    $cfg          = $settings.Configuration

    $cfg.ResourceGroup = Read-Required -Prompt "Resource group name" -Default $cfg.ResourceGroup
    $cfg.Subscription  = Read-Required -Prompt "Subscription ID"     -Default $cfg.Subscription
    $cfg.DesiredTenant = Read-Required -Prompt "Tenant ID"           -Default $cfg.DesiredTenant

    Write-Host ""
    Write-Host "  Validation mode:" -ForegroundColor White
    Write-Host "  [1] All      -- validate before every deployment" -ForegroundColor Gray
    Write-Host "  [2] Changed  -- only validate changed files"       -ForegroundColor Gray
    Write-Host "  [3] Skip     -- no validation"                     -ForegroundColor Gray
    $modes   = @("All", "Changed", "Skip")
    $currIdx = ([array]::IndexOf($modes, $cfg.ValidationMode) + 1).ToString()
    $sel     = Read-WithDefault -Prompt "Select [1-3]" -Default $currIdx
    $cfg.ValidationMode = $modes[[int]$sel - 1]

    $cfg.ConsoleWidth = [int](Read-WithDefault -Prompt "Console width" -Default "$($cfg.ConsoleWidth)")

    $output = [PSCustomObject]@{
        SelectedParameterFile = $settings.SelectedParameterFile
        LastUpdated           = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        FileOrder             = $settings.FileOrder
        Configuration         = $cfg
    }

    $output | ConvertTo-Json -Depth 10 | Set-Content $settingsPath
    Write-Host ""
    Write-Host "  Saved: $settingsPath" -ForegroundColor Green
    Write-Host ""
}

#endregion

#region Mode 2 -- Parameters file (parameters.{env}.json)

function Invoke-Mode2 {
    Write-Host ""
    Write-Host "  Parameters File Setup" -ForegroundColor Cyan
    Write-Host ""

    $envName   = Read-Required -Prompt "Environment name (e.g. local, dev, prod)"
    $paramFile = Join-Path $ProjectPath "parameters.$envName.json"

    $templatePath = Join-Path $PSScriptRoot "templates\parameters.template.json"
    if (-not (Test-Path $templatePath)) {
        Write-Host "  Template not found at: $templatePath" -ForegroundColor Red
        exit 1
    }

    if (Test-Path $paramFile) {
        Write-Host "  Loading existing: $paramFile" -ForegroundColor Gray
        $params = Get-Content $paramFile -Raw | ConvertFrom-Json
    } else {
        Write-Host "  Creating new from template." -ForegroundColor Gray
        $params = Get-Content $templatePath -Raw | ConvertFrom-Json
    }

    $p = $params.parameters

    # -- Critical fields --
    Write-Host ""
    Write-Host "  -- Critical Fields --" -ForegroundColor White

    $envCurr = if ($p.environment.value -ne '<PLACEHOLDER>') { " [$($p.environment.value)]" } else { " (required)" }
    $p.environment.value = Read-Required -Prompt "environment (e.g. test, prod)$envCurr"

    $sufCurr = if ($p.projectSuffix.value -ne '<PLACEHOLDER>') { " [$($p.projectSuffix.value)]" } else { " (required)" }
    $p.projectSuffix.value = Read-Required -Prompt "projectSuffix$sufCurr"

    $dvUriCurr = if ($p.dataverse.value.uri -ne '<PLACEHOLDER>') { " [$($p.dataverse.value.uri)]" } else { " (required)" }
    $p.dataverse.value.uri = Read-Required -Prompt "dataverse.uri$dvUriCurr"

    $dvIdCurr = if ($p.dataverse.value.clientId -ne '<PLACEHOLDER>') { " [$($p.dataverse.value.clientId)]" } else { " (required)" }
    $p.dataverse.value.clientId = Read-Required -Prompt "dataverse.clientId$dvIdCurr"

    $bcEnvCurr = if ($p.businessCentral.value.environmentName -ne '<PLACEHOLDER>') { " [$($p.businessCentral.value.environmentName)]" } else { " (required)" }
    $p.businessCentral.value.environmentName = Read-Required -Prompt "businessCentral.environmentName$bcEnvCurr"

    # -- Countries (dynamic) --
    Write-Host ""
    Write-Host "  -- Business Central Countries --" -ForegroundColor White

    $countries = [System.Collections.Generic.List[object]]@()
    if ($p.businessCentral.value.countries) {
        foreach ($c in $p.businessCentral.value.countries) { $countries.Add($c) }
    }
    if ($countries.Count -eq 0) {
        $countries.Add([PSCustomObject]@{
            name                = "denmark"
            companyId           = "<PLACEHOLDER>"
            serviceAccountGuid  = "<PLACEHOLDER>"
            systemReferenceGuid = "<PLACEHOLDER>"
        })
        Write-Host "  Defaulted to Denmark entry." -ForegroundColor Gray
    }

    :countryLoop while ($true) {
        Write-Host ""
        Write-Host "  Current countries:" -ForegroundColor Gray
        for ($i = 0; $i -lt $countries.Count; $i++) {
            Write-Host "  [$($i+1)] $($countries[$i].name)  companyId: $($countries[$i].companyId)" -ForegroundColor White
        }
        Write-Host ""
        Write-Host "  [A] Add   [R] Remove   [D] Done" -ForegroundColor Gray
        $action = (Read-Host "  Action").ToUpper()

        switch ($action) {
            "A" {
                $name      = Read-Required   -Prompt "Country name"
                $companyId = Read-WithDefault -Prompt "companyId" -Default "<PLACEHOLDER>"
                $countries.Add([PSCustomObject]@{
                    name                = $name
                    companyId           = $companyId
                    serviceAccountGuid  = "<PLACEHOLDER>"
                    systemReferenceGuid = "<PLACEHOLDER>"
                })
            }
            "R" {
                if ($countries.Count -le 1) {
                    Write-Host "  Must keep at least one country." -ForegroundColor Red
                } else {
                    $removeInput = Read-Host "  Remove number"
                    $removeNum = 0
                    if (-not [int]::TryParse($removeInput, [ref]$removeNum) -or $removeNum -lt 1 -or $removeNum -gt $countries.Count) {
                        Write-Host "  Invalid number." -ForegroundColor Red
                    } else {
                        $countries.RemoveAt($removeNum - 1)
                    }
                }
            }
            "D" { break countryLoop }
            default { Write-Host "  Unknown action." -ForegroundColor Red }
        }
    }

    $p.businessCentral.value | Add-Member -MemberType NoteProperty -Name countries -Value $countries.ToArray() -Force

    # Write file
    $params.parameters = $p
    $params | ConvertTo-Json -Depth 20 | Set-Content $paramFile
    Write-Host ""
    Write-Host "  Saved: $paramFile" -ForegroundColor Green

    # Print remaining placeholders
    $remaining = Get-PlaceholderFields -Obj $params -Path ""
    if ($remaining.Count -gt 0) {
        Write-Host ""
        Write-Host "  The following fields still need manual values:" -ForegroundColor Yellow
        foreach ($field in $remaining) { Write-Host "  - $field" -ForegroundColor Gray }
    }

    # .gitignore offer
    Write-Host ""
    Write-Host "  parameters.*.json files contain secrets -- do not commit them." -ForegroundColor Yellow
    $ans = Read-Host "  Add 'parameters.*.json' to .gitignore automatically? [Y/n]"
    if ($ans -ne 'n') {
        Add-GitIgnoreEntry -ProjectPath $ProjectPath -Entry "parameters.*.json"
    }

    Write-Host ""
}

#endregion

#region Entry point

Write-Host ""
Write-Host "  bicepDeployment Setup" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [1] Deployment settings (.deployment-settings.json)" -ForegroundColor White
Write-Host "  [2] Parameters file (parameters.{env}.json)"         -ForegroundColor White
Write-Host ""
$choice = Read-Host "  Select [1-2]"

switch ($choice) {
    "1" { Invoke-Mode1 }
    "2" { Invoke-Mode2 }
    default { Write-Host "  Invalid selection." -ForegroundColor Red; exit 1 }
}

#endregion
