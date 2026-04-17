#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0' }

BeforeAll {
    . "$PSScriptRoot/../_helpers.ps1"
}

Describe "Test-IsToolRoot" {
    It "returns true when deployScript/main.py exists" {
        $tmpDir = Join-Path $env:TEMP "bicep-test-$([System.Guid]::NewGuid())"
        New-Item -ItemType Directory -Path "$tmpDir\deployScript" -Force | Out-Null
        New-Item -ItemType File     -Path "$tmpDir\deployScript\main.py" -Force | Out-Null
        Test-IsToolRoot -Path $tmpDir | Should -BeTrue
        Remove-Item -Recurse -Force $tmpDir
    }

    It "returns false when deployScript/main.py does not exist" {
        $tmpDir = Join-Path $env:TEMP "bicep-test-$([System.Guid]::NewGuid())"
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        Test-IsToolRoot -Path $tmpDir | Should -BeFalse
        Remove-Item -Recurse -Force $tmpDir
    }
}

Describe "Get-RelativePath" {
    It "returns correct relative path for sibling folders" {
        $from = "D:\repos\MyProject"
        $to   = "D:\repos\bicepDeployment"
        Get-RelativePath -From $from -To $to | Should -Be "..\bicepDeployment"
    }

    It "returns correct relative path for nested project" {
        $from = "D:\repos\client\MyProject"
        $to   = "D:\repos\bicepDeployment"
        Get-RelativePath -From $from -To $to | Should -Be "..\..\bicepDeployment"
    }
}

Describe "Test-WorkspaceReferencesBicep" {
    It "returns true when bicepDeployment is listed in folders" {
        $ws = [PSCustomObject]@{
            folders = @(
                [PSCustomObject]@{ path = "." },
                [PSCustomObject]@{ path = "..\bicepDeployment" }
            )
        }
        Test-WorkspaceReferencesBicep -Workspace $ws -BicepRelPath "..\bicepDeployment" | Should -BeTrue
    }

    It "returns false when not referenced" {
        $ws = [PSCustomObject]@{ folders = @([PSCustomObject]@{ path = "." }) }
        Test-WorkspaceReferencesBicep -Workspace $ws -BicepRelPath "..\bicepDeployment" | Should -BeFalse
    }
}

Describe "Add-GitIgnoreEntry" {
    It "creates .gitignore with entry when file does not exist" {
        $tmpDir = Join-Path $env:TEMP "bicep-test-$([System.Guid]::NewGuid())"
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        Add-GitIgnoreEntry -ProjectPath $tmpDir -Entry "parameters.*.json"
        $content = Get-Content (Join-Path $tmpDir ".gitignore") -Raw
        $content | Should -Match "parameters\.\*\.json"
        Remove-Item -Recurse -Force $tmpDir
    }

    It "appends entry when .gitignore exists but does not contain it" {
        $tmpDir = Join-Path $env:TEMP "bicep-test-$([System.Guid]::NewGuid())"
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        Set-Content (Join-Path $tmpDir ".gitignore") "*.log"
        Add-GitIgnoreEntry -ProjectPath $tmpDir -Entry "parameters.*.json"
        $content = Get-Content (Join-Path $tmpDir ".gitignore") -Raw
        $content | Should -Match "parameters\.\*\.json"
        Remove-Item -Recurse -Force $tmpDir
    }

    It "does not duplicate entry when already present" {
        $tmpDir = Join-Path $env:TEMP "bicep-test-$([System.Guid]::NewGuid())"
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        Set-Content (Join-Path $tmpDir ".gitignore") "parameters.*.json"
        Add-GitIgnoreEntry -ProjectPath $tmpDir -Entry "parameters.*.json"
        $lines = Get-Content (Join-Path $tmpDir ".gitignore") | Where-Object { $_ -eq "parameters.*.json" }
        $lines.Count | Should -Be 1
        Remove-Item -Recurse -Force $tmpDir
    }
}
