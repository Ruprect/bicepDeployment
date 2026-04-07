#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0' }

BeforeAll {
    . "$PSScriptRoot/../_helpers.ps1"
    . "$PSScriptRoot/../setup.ps1" -LoadHelpersOnly
}

Describe "Read-WithDefault" {
    It "returns input when non-empty" {
        Mock Read-Host { return "myvalue" }
        Read-WithDefault -Prompt "Test" -Default "fallback" | Should -Be "myvalue"
    }

    It "returns default when input is empty" {
        Mock Read-Host { return "" }
        Read-WithDefault -Prompt "Test" -Default "fallback" | Should -Be "fallback"
    }
}

Describe "Get-DeploymentSettings" {
    It "returns defaults when file does not exist" {
        $s = Get-DeploymentSettings -Path "C:\nonexistent\settings.json"
        $s.Configuration.ValidationMode | Should -Be "All"
        $s.Configuration.ConsoleWidth   | Should -Be 75
        $s.FileOrder.Count              | Should -Be 0
    }

    It "preserves FileOrder from existing file" {
        $tmpFile = Join-Path $env:TEMP "test-settings-$(New-Guid).json"
        [PSCustomObject]@{
            FileOrder     = @([PSCustomObject]@{ FileName = "test.bicep" })
            Configuration = [PSCustomObject]@{ ResourceGroup = "rg"; ValidationMode = "All"; ConsoleWidth = 75 }
        } | ConvertTo-Json -Depth 10 | Set-Content $tmpFile

        $s = Get-DeploymentSettings -Path $tmpFile
        $s.FileOrder.Count         | Should -Be 1
        $s.FileOrder[0].FileName   | Should -Be "test.bicep"
        Remove-Item $tmpFile
    }

    It "fills missing Configuration keys with defaults" {
        $tmpFile = Join-Path $env:TEMP "test-settings-$(New-Guid).json"
        [PSCustomObject]@{
            FileOrder     = @()
            Configuration = [PSCustomObject]@{ ResourceGroup = "myRg" }
        } | ConvertTo-Json -Depth 10 | Set-Content $tmpFile

        $s = Get-DeploymentSettings -Path $tmpFile
        $s.Configuration.ResourceGroup  | Should -Be "myRg"
        $s.Configuration.ValidationMode | Should -Be "All"
        $s.Configuration.ConsoleWidth   | Should -Be 75
        Remove-Item $tmpFile
    }
}

Describe "Get-PlaceholderFields" {
    It "returns paths of fields containing <PLACEHOLDER>" {
        $obj = '{"parameters":{"environment":{"value":"<PLACEHOLDER>"},"projectSuffix":{"value":"myproj"},"dataverse":{"value":{"uri":"<PLACEHOLDER>","clientId":"real"}}}}' | ConvertFrom-Json
        $fields = Get-PlaceholderFields -Obj $obj -Path ""
        $fields | Should -Contain "parameters.environment.value"
        $fields | Should -Contain "parameters.dataverse.value.uri"
        $fields | Should -Not -Contain "parameters.projectSuffix.value"
        $fields | Should -Not -Contain "parameters.dataverse.value.clientId"
    }
}
