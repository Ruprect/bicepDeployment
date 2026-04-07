# ============================================================
# FILE: Modules\UI-Dialogs.ps1
# ============================================================

function Show-ParameterFileDialog {
    $paramFiles = Get-ChildItem -Path "." -Filter "parameters.*.json" | Sort-Object Name
    
    if ($paramFiles.Count -eq 0) {
        [System.Windows.MessageBox]::Show("No parameter files found!", "Warning", "OK", "Warning")
        return
    }
    
    $selected = $paramFiles | Select-Object Name, @{N='Size (KB)';E={[math]::Round($_.Length / 1KB, 2)}}, LastWriteTime | 
        Out-GridView -Title "Select Parameter File" -OutputMode Single
    
    if ($selected) {
        $config = Load-DeploymentSettings
        $config.SelectedParameterFile = $selected.Name
        Save-DeploymentSettings $config
        Update-MainUI
        [System.Windows.MessageBox]::Show("Parameter file selected: $($selected.Name)", "Success", "OK", "Information")
    }
}

function Show-ReorderDialog {
    $xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="Reorder Templates" Height="600" Width="700"
        WindowStartupLocation="CenterScreen" Background="#1E1E1E">
    <Grid Margin="20">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        
        <StackPanel Grid.Row="0" Margin="0,0,0,15">
            <TextBlock Text="Reorder Templates" FontSize="20" FontWeight="Bold" Foreground="#569CD6"/>
            <TextBlock Text="Drag templates to reorder. Changes save automatically." Foreground="#9CDCFE" Margin="0,5,0,0"/>
        </StackPanel>
        
        <ListBox Name="TemplateList" Grid.Row="1"
                 Background="#252526"
                 BorderBrush="#3F3F46"
                 AllowDrop="True">
            <ListBox.ItemContainerStyle>
                <Style TargetType="ListBoxItem">
                    <Setter Property="Background" Value="#2D2D30"/>
                    <Setter Property="Foreground" Value="White"/>
                    <Setter Property="Padding" Value="10"/>
                    <Setter Property="Margin" Value="0,2"/>
                    <Setter Property="BorderThickness" Value="0"/>
                    <Style.Triggers>
                        <Trigger Property="IsMouseOver" Value="True">
                            <Setter Property="Background" Value="#3E3E42"/>
                        </Trigger>
                        <Trigger Property="IsSelected" Value="True">
                            <Setter Property="Background" Value="#094771"/>
                        </Trigger>
                    </Style.Triggers>
                </Style>
            </ListBox.ItemContainerStyle>
        </ListBox>
        
        <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,15,0,0">
            <Button Name="MoveUpButton" Content="Move Up" Width="100" Margin="0,0,10,0"/>
            <Button Name="MoveDownButton" Content="Move Down" Width="100" Margin="0,0,10,0"/>
            <Button Name="CloseButton" Content="Close" Width="100"/>
        </StackPanel>
    </Grid>
</Window>
"@

    $dialog = [Windows.Markup.XamlReader]::Parse($xaml)
    $templateList = $dialog.FindName("TemplateList")
    $moveUpButton = $dialog.FindName("MoveUpButton")
    $moveDownButton = $dialog.FindName("MoveDownButton")
    $closeButton = $dialog.FindName("CloseButton")
    
    # Populate list
    $templates = Get-BicepTemplates
    foreach ($template in $templates) {
        $statusIcon = if ($template.Size -eq 0) { "⚫" }
                     elseif ($null -eq $template.LastDeploymentSuccess) { "⚪" }
                     elseif ($template.LastDeploymentSuccess -eq $false) { "🔴" }
                     elseif ($template.NeedsRedeployment) { "🟡" }
                     else { "🟢" }
        
        $enableIcon = if ($template.Enabled) { "✓" } else { "✗" }
        $item = "$statusIcon $enableIcon $($template.Name)"
        [void]$templateList.Items.Add($item)
    }
    
    # Move Up
    $moveUpButton.Add_Click({
        $idx = $templateList.SelectedIndex
        if ($idx -gt 0) {
            $item = $templateList.Items[$idx]
            $templateList.Items.RemoveAt($idx)
            $templateList.Items.Insert($idx - 1, $item)
            $templateList.SelectedIndex = $idx - 1
            
            # Swap in templates array
            $temp = $templates[$idx]
            $templates[$idx] = $templates[$idx - 1]
            $templates[$idx - 1] = $temp
            
            Save-TemplateOrder -Templates $templates
        }
    })
    
    # Move Down
    $moveDownButton.Add_Click({
        $idx = $templateList.SelectedIndex
        if ($idx -ge 0 -and $idx -lt $templateList.Items.Count - 1) {
            $item = $templateList.Items[$idx]
            $templateList.Items.RemoveAt($idx)
            $templateList.Items.Insert($idx + 1, $item)
            $templateList.SelectedIndex = $idx + 1
            
            # Swap in templates array
            $temp = $templates[$idx]
            $templates[$idx] = $templates[$idx + 1]
            $templates[$idx + 1] = $temp
            
            Save-TemplateOrder -Templates $templates
        }
    })
    
    $closeButton.Add_Click({
        Update-MainUI
        $dialog.Close()
    })
    
    [void]$dialog.ShowDialog()
}