# ============================================================
# FILE: Modules\UI-MainWindow.ps1
# ============================================================

<#
.SYNOPSIS
    Main window UI module
#>

function Show-MainWindow {
    $xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Azure BICEP Deployment Tool" Height="750" Width="1100"
        WindowStartupLocation="CenterScreen" Background="#1E1E1E">
    <Window.Resources>
        <Style TargetType="Button">
            <Setter Property="Background" Value="#0E639C"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Padding" Value="15,8"/>
            <Setter Property="Margin" Value="5"/>
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="Cursor" Value="Hand"/>
            <Style.Triggers>
                <Trigger Property="IsMouseOver" Value="True">
                    <Setter Property="Background" Value="#1177BB"/>
                </Trigger>
            </Style.Triggers>
        </Style>
        <Style TargetType="TextBlock">
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="FontSize" Value="12"/>
        </Style>
    </Window.Resources>
    
    <Grid Margin="15">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        
        <!-- Header -->
        <Border Grid.Row="0" Background="#252526" Padding="15" Margin="0,0,0,10" CornerRadius="5">
            <StackPanel>
                <TextBlock Text="Azure BICEP Deployment Tool" FontSize="22" FontWeight="Bold" Foreground="#569CD6"/>
                <TextBlock Name="StatusText" Text="Loading..." Margin="0,8,0,0" Foreground="#9CDCFE" FontSize="13"/>
            </StackPanel>
        </Border>
        
        <!-- Configuration Panel -->
        <Border Grid.Row="1" Background="#252526" Padding="12" Margin="0,0,0,10" CornerRadius="5">
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>
                <StackPanel Grid.Column="0">
                    <TextBlock Name="ResourceGroupText" Text="Resource Group: Not set" FontSize="13"/>
                    <TextBlock Name="ParameterFileText" Text="Parameter File: None" Margin="0,5,0,0" FontSize="13"/>
                    <TextBlock Name="ValidationModeText" Text="Validation: All" Margin="0,5,0,0" FontSize="13"/>
                </StackPanel>
                <StackPanel Grid.Column="1" Orientation="Horizontal">
                    <Button Name="ConfigButton" Content="⚙️ Configure" Width="120"/>
                    <Button Name="RefreshButton" Content="🔄 Refresh" Width="120"/>
                </StackPanel>
            </Grid>
        </Border>
        
        <!-- Templates DataGrid -->
        <Border Grid.Row="2" Background="#252526" Padding="12" CornerRadius="5">
            <Grid>
                <Grid.RowDefinitions>
                    <RowDefinition Height="Auto"/>
                    <RowDefinition Height="*"/>
                </Grid.RowDefinitions>
                <DockPanel Grid.Row="0" Margin="0,0,0,10">
                    <TextBlock Text="BICEP Templates" FontSize="15" FontWeight="Bold" Foreground="#569CD6" VerticalAlignment="Center"/>
                    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
                        <TextBlock Text="🟢 Up-to-date   " Foreground="#4EC9B0" VerticalAlignment="Center" Margin="10,0,0,0"/>
                        <TextBlock Text="🟡 Changed   " Foreground="#DCDCAA" VerticalAlignment="Center"/>
                        <TextBlock Text="🔴 Failed   " Foreground="#F48771" VerticalAlignment="Center"/>
                        <TextBlock Text="⚪ Never   " Foreground="#CCCCCC" VerticalAlignment="Center"/>
                        <TextBlock Text="⚫ Empty" Foreground="#808080" VerticalAlignment="Center"/>
                    </StackPanel>
                </DockPanel>
                <DataGrid Name="TemplatesGrid" Grid.Row="1" 
                          AutoGenerateColumns="False" 
                          CanUserAddRows="False"
                          CanUserDeleteRows="False"
                          CanUserReorderColumns="True"
                          CanUserSortColumns="False"
                          SelectionMode="Single"
                          Background="#1E1E1E"
                          RowBackground="#2D2D30"
                          AlternatingRowBackground="#252526"
                          BorderBrush="#3F3F46"
                          GridLinesVisibility="Horizontal"
                          HorizontalGridLinesBrush="#3F3F46"
                          HeadersVisibility="Column"
                          FontSize="12">
                    <DataGrid.Columns>
                        <DataGridTemplateColumn Header="✓" Width="45">
                            <DataGridTemplateColumn.CellTemplate>
                                <DataTemplate>
                                    <CheckBox IsChecked="{Binding Enabled, Mode=TwoWay, UpdateSourceTrigger=PropertyChanged}" 
                                              HorizontalAlignment="Center" VerticalAlignment="Center"/>
                                </DataTemplate>
                            </DataGridTemplateColumn.CellTemplate>
                        </DataGridTemplateColumn>
                        <DataGridTextColumn Header="Status" Binding="{Binding StatusIcon}" Width="60" IsReadOnly="True"/>
                        <DataGridTextColumn Header="Template Name" Binding="{Binding Name}" Width="*" IsReadOnly="True"/>
                        <DataGridTextColumn Header="Size (KB)" Binding="{Binding SizeKB}" Width="90" IsReadOnly="True"/>
                        <DataGridTextColumn Header="Last Modified" Binding="{Binding LastModifiedStr}" Width="150" IsReadOnly="True"/>
                    </DataGrid.Columns>
                    <DataGrid.ColumnHeaderStyle>
                        <Style TargetType="DataGridColumnHeader">
                            <Setter Property="Background" Value="#007ACC"/>
                            <Setter Property="Foreground" Value="White"/>
                            <Setter Property="FontWeight" Value="Bold"/>
                            <Setter Property="Padding" Value="10,8"/>
                            <Setter Property="BorderThickness" Value="0,0,1,0"/>
                            <Setter Property="BorderBrush" Value="#1E1E1E"/>
                        </Style>
                    </DataGrid.ColumnHeaderStyle>
                    <DataGrid.CellStyle>
                        <Style TargetType="DataGridCell">
                            <Setter Property="Foreground" Value="White"/>
                            <Setter Property="Background" Value="Transparent"/>
                            <Setter Property="BorderThickness" Value="0"/>
                            <Setter Property="Padding" Value="8,5"/>
                        </Style>
                    </DataGrid.CellStyle>
                </DataGrid>
            </Grid>
        </Border>
        
        <!-- Progress Panel -->
        <Border Grid.Row="3" Background="#252526" Padding="12" Margin="0,10,0,0" CornerRadius="5" Name="ProgressPanel" Visibility="Collapsed">
            <StackPanel>
                <TextBlock Name="ProgressText" Text="Processing..." FontWeight="Bold" FontSize="13"/>
                <ProgressBar Name="ProgressBar" Height="24" Margin="0,8,0,0" Minimum="0" Maximum="100"/>
            </StackPanel>
        </Border>
        
        <!-- Action Buttons -->
        <Border Grid.Row="4" Background="#252526" Padding="12" Margin="0,10,0,0" CornerRadius="5">
            <WrapPanel HorizontalAlignment="Center">
                <Button Name="DeployAllButton" Content="🚀 Deploy All" Width="140"/>
                <Button Name="ValidateAllButton" Content="✅ Validate All" Width="140"/>
                <Button Name="SelectParamButton" Content="📄 Parameters" Width="140"/>
                <Button Name="ReorderButton" Content="↕️ Reorder" Width="140"/>
                <Button Name="ToggleValidationButton" Content="🔄 Validation Mode" Width="160"/>
            </WrapPanel>
        </Border>
    </Grid>
</Window>
"@

    $window = [Windows.Markup.XamlReader]::Parse($xaml)
    
    # Get controls
    $script:MainWindow = $window
    $script:StatusText = $window.FindName("StatusText")
    $script:ResourceGroupText = $window.FindName("ResourceGroupText")
    $script:ParameterFileText = $window.FindName("ParameterFileText")
    $script:ValidationModeText = $window.FindName("ValidationModeText")
    $script:TemplatesGrid = $window.FindName("TemplatesGrid")
    $script:ProgressPanel = $window.FindName("ProgressPanel")
    $script:ProgressBar = $window.FindName("ProgressBar")
    $script:ProgressText = $window.FindName("ProgressText")
    
    # Initialize Azure client
    $script:AzureClient = [AzureClient]::new()
    $script:Templates = @()
    
    # Setup event handlers
    $window.FindName("RefreshButton").Add_Click({ Update-MainUI })
    $window.FindName("ConfigButton").Add_Click({ Show-ConfigDialog; Update-MainUI })
    $window.FindName("SelectParamButton").Add_Click({ Show-ParameterFileDialog })
    $window.FindName("ToggleValidationButton").Add_Click({ Toggle-ValidationMode })
    $window.FindName("DeployAllButton").Add_Click({ Start-DeployAll })
    $window.FindName("ValidateAllButton").Add_Click({ Start-ValidateAll })
    $window.FindName("ReorderButton").Add_Click({ Show-ReorderDialog })
    
    # Initial update
    Update-MainUI
    
    # Show window
    [void]$window.ShowDialog()
}

function Update-MainUI {
    # Update Azure status
    if ($script:AzureClient.TestLogin()) {
        $tenantInfo = $script:AzureClient.GetTenantInfo()
        $script:StatusText.Text = "Azure: ✅ Connected - $($tenantInfo.SubscriptionName)"
    }
    else {
        $script:StatusText.Text = "Azure: ❌ Not logged in - Use Configure to login"
    }
    
    # Update configuration
    $rg = Get-ConfigValue -Key "ResourceGroup" -Default "Not set"
    $script:ResourceGroupText.Text = "🏢 Resource Group: $rg"
    
    $config = Load-DeploymentSettings
    if ($config.SelectedParameterFile) {
        $script:ParameterFileText.Text = "📄 Parameter File: $($config.SelectedParameterFile)"
    }
    else {
        $script:ParameterFileText.Text = "📄 Parameter File: None selected"
    }
    
    $validationMode = Get-ConfigValue -Key "ValidationMode" -Default "All"
    $script:ValidationModeText.Text = "🔍 Validation: $validationMode"
    
    # Update templates
    $script:Templates = Get-BicepTemplates
    $gridData = $script:Templates | ForEach-Object {
        $statusIcon = if ($_.Size -eq 0) { "⚫" }
                     elseif ($null -eq $_.LastDeploymentSuccess) { "⚪" }
                     elseif ($_.LastDeploymentSuccess -eq $false) { "🔴" }
                     elseif ($_.NeedsRedeployment) { "🟡" }
                     else { "🟢" }
        
        [PSCustomObject]@{
            Enabled = $_.Enabled
            StatusIcon = $statusIcon
            Name = $_.Name
            SizeKB = [math]::Round($_.Size / 1KB, 2)
            LastModifiedStr = $_.LastModified.ToString("yyyy-MM-dd HH:mm")
            Template = $_
        }
    }
    $script:TemplatesGrid.ItemsSource = $gridData
}

function Toggle-ValidationMode {
    $current = Get-ConfigValue -Key "ValidationMode" -Default "All"
    $new = switch ($current) {
        "All" { "Changed" }
        "Changed" { "Skip" }
        "Skip" { "All" }
    }
    Set-ConfigValue -Key "ValidationMode" -Value $new
    Update-MainUI
}

function Start-DeployAll {
    $config = Load-DeploymentSettings
    $rg = Get-ConfigValue -Key "ResourceGroup"
    
    if (-not $rg) {
        [System.Windows.MessageBox]::Show("Please set a resource group first!", "Error", "OK", "Error")
        return
    }
    
    $enabled = $script:Templates | Where-Object { $_.Enabled -and $_.Size -gt 0 }
    if ($enabled.Count -eq 0) {
        [System.Windows.MessageBox]::Show("No enabled templates to deploy!", "Warning", "OK", "Warning")
        return
    }
    
    $result = [System.Windows.MessageBox]::Show("Deploy $($enabled.Count) template(s)?", "Confirm Deployment", "YesNo", "Question")
    if ($result -ne "Yes") { return }
    
    # Show progress
    $script:ProgressPanel.Visibility = "Visible"
    $script:ProgressBar.Value = 0
    
    $success = 0
    $failed = 0
    
    for ($i = 0; $i -lt $enabled.Count; $i++) {
        $template = $enabled[$i]
        $script:ProgressText.Text = "Deploying $($template.Name) ($($i+1)/$($enabled.Count))..."
        $script:ProgressBar.Value = (($i + 1) / $enabled.Count) * 100
        $script:MainWindow.Dispatcher.Invoke([action]{}, "Render")
        
        $mode = "Incremental"
        $deployResult = $script:AzureClient.DeployTemplate($rg, $template.File, $config.SelectedParameterFile, $mode)
        
        if ($deployResult.Success) {
            $success++
            Update-DeploymentHistory -TemplateName $template.Name -Success $true
        }
        else {
            $failed++
            Update-DeploymentHistory -TemplateName $template.Name -Success $false -ErrorMessage $deployResult.Message
        }
    }
    
    $script:ProgressPanel.Visibility = "Collapsed"
    Update-MainUI
    
    [System.Windows.MessageBox]::Show("Deployment Complete!`n`n✅ Success: $success`n❌ Failed: $failed", "Results", "OK", "Information")
}

function Start-ValidateAll {
    $rg = Get-ConfigValue -Key "ResourceGroup"
    
    if (-not $rg) {
        [System.Windows.MessageBox]::Show("Please set a resource group first!", "Error", "OK", "Error")
        return
    }
    
    $enabled = $script:Templates | Where-Object { $_.Enabled -and $_.Size -gt 0 }
    if ($enabled.Count -eq 0) {
        [System.Windows.MessageBox]::Show("No enabled templates to validate!", "Warning", "OK", "Warning")
        return
    }
    
    $script:ProgressPanel.Visibility = "Visible"
    $config = Load-DeploymentSettings
    $results = @()
    
    for ($i = 0; $i -lt $enabled.Count; $i++) {
        $template = $enabled[$i]
        $script:ProgressText.Text = "Validating $($template.Name) ($($i+1)/$($enabled.Count))..."
        $script:ProgressBar.Value = (($i + 1) / $enabled.Count) * 100
        $script:MainWindow.Dispatcher.Invoke([action]{}, "Render")
        
        $valResult = $script:AzureClient.ValidateTemplate($rg, $template.File, $config.SelectedParameterFile)
        $results += [PSCustomObject]@{
            Template = $template.Name
            Result = if ($valResult.Success) { "✅ Passed" } else { "❌ Failed" }
            Message = $valResult.Message
        }
    }
    
    $script:ProgressPanel.Visibility = "Collapsed"
    $results | Out-GridView -Title "Validation Results" -Wait
}