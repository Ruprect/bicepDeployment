# ============================================================
# FILE: Modules\UI-ConfigDialog.ps1
# ============================================================

function Show-ConfigDialog {
    $xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="Azure Configuration" Height="550" Width="650"
        WindowStartupLocation="CenterScreen" Background="#1E1E1E">
    <Grid Margin="20">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        
        <TextBlock Grid.Row="0" Text="Azure Configuration" FontSize="20" FontWeight="Bold" Foreground="#569CD6" Margin="0,0,0,20"/>
        
        <ScrollViewer Grid.Row="1" VerticalScrollBarVisibility="Auto">
            <StackPanel>
                <GroupBox Header="Azure Status" Foreground="White" Margin="0,0,0,15" Padding="10" Background="#252526">
                    <StackPanel>
                        <TextBlock Name="AzureStatus" Text="Checking..." Foreground="White" Margin="0,0,0,10"/>
                        <Button Name="LoginButton" Content="Azure Login" Width="150" HorizontalAlignment="Left"/>
                    </StackPanel>
                </GroupBox>
                
                <GroupBox Header="Resource Group" Foreground="White" Margin="0,0,0,15" Padding="10" Background="#252526">
                    <StackPanel>
                        <TextBlock Name="CurrentRG" Text="Current: Not set" Foreground="White" Margin="0,0,0,10"/>
                        <Button Name="SelectRGButton" Content="Select Resource Group" Width="180" HorizontalAlignment="Left"/>
                    </StackPanel>
                </GroupBox>
                
                <GroupBox Header="Subscription" Foreground="White" Margin="0,0,0,15" Padding="10" Background="#252526">
                    <StackPanel>
                        <TextBlock Name="CurrentSub" Text="Current: Not set" Foreground="White" Margin="0,0,0,10"/>
                        <Button Name="SelectSubButton" Content="Select Subscription" Width="180" HorizontalAlignment="Left"/>
                    </StackPanel>
                </GroupBox>
                
                <GroupBox Header="Tenant" Foreground="White" Margin="0,0,0,15" Padding="10" Background="#252526">
                    <StackPanel>
                        <TextBlock Name="CurrentTenant" Text="Current: Not set" Foreground="White" Margin="0,0,0,10"/>
                        <TextBox Name="TenantInput" Background="#1E1E1E" Foreground="White" Margin="0,0,0,10" Padding="5"/>
                        <Button Name="SetTenantButton" Content="Set Tenant ID" Width="150" HorizontalAlignment="Left"/>
                    </StackPanel>
                </GroupBox>
            </StackPanel>
        </ScrollViewer>
        
        <Button Grid.Row="2" Content="Close" Width="100" HorizontalAlignment="Right" Name="CloseButton"/>
    </Grid>
</Window>
"@

    $dialog = [Windows.Markup.XamlReader]::Parse($xaml)
    
    # Get controls
    $azureStatus = $dialog.FindName("AzureStatus")
    $loginButton = $dialog.FindName("LoginButton")
    $currentRG = $dialog.FindName("CurrentRG")
    $selectRGButton = $dialog.FindName("SelectRGButton")
    $currentSub = $dialog.FindName("CurrentSub")
    $selectSubButton = $dialog.FindName("SelectSubButton")
    $currentTenant = $dialog.FindName("CurrentTenant")
    $tenantInput = $dialog.FindName("TenantInput")
    $setTenantButton = $dialog.FindName("SetTenantButton")
    $closeButton = $dialog.FindName("CloseButton")
    
    # Update status
    function Update-ConfigDialogStatus {
        if ($script:AzureClient.TestLogin()) {
            $tenantInfo = $script:AzureClient.GetTenantInfo()
            $azureStatus.Text = "Status: Connected`nSubscription: $($tenantInfo.SubscriptionName)`nTenant: $($tenantInfo.TenantId)"
        }
        else {
            $azureStatus.Text = "Status: Not logged in"
        }
        
        $rg = Get-ConfigValue -Key "ResourceGroup" -Default "Not set"
        $currentRG.Text = "Current: $rg"
        
        $sub = Get-ConfigValue -Key "Subscription" -Default "Not set"
        $currentSub.Text = "Current: $sub"
        
        $tenant = Get-ConfigValue -Key "DesiredTenant" -Default "Not set"
        $currentTenant.Text = "Current: $tenant"
        $tenantInput.Text = if ($tenant -ne "Not set") { $tenant } else { "" }
    }
    
    # Event handlers
    $loginButton.Add_Click({
        $tenant = Get-ConfigValue -Key "DesiredTenant"
        if ($script:AzureClient.Login($tenant)) {
            [System.Windows.MessageBox]::Show("Login successful!", "Success", "OK", "Information")
            Update-ConfigDialogStatus
        }
        else {
            [System.Windows.MessageBox]::Show("Login failed", "Error", "OK", "Error")
        }
    })
    
    $selectRGButton.Add_Click({
        $groups = $script:AzureClient.GetResourceGroups()
        if ($groups.Count -eq 0) {
            [System.Windows.MessageBox]::Show("No resource groups found. Please login first.", "Warning", "OK", "Warning")
            return
        }
        
        $selected = $groups | Select-Object name, location, @{N='State';E={$_.properties.provisioningState}} | 
            Out-GridView -Title "Select Resource Group" -OutputMode Single
        
        if ($selected) {
            Set-ConfigValue -Key "ResourceGroup" -Value $selected.name
            Update-ConfigDialogStatus
        }
    })
    
    $selectSubButton.Add_Click({
        $subs = $script:AzureClient.GetSubscriptions()
        if ($subs.Count -eq 0) {
            [System.Windows.MessageBox]::Show("No subscriptions found. Please login first.", "Warning", "OK", "Warning")
            return
        }
        
        $selected = $subs | Select-Object name, id, state | 
            Out-GridView -Title "Select Subscription" -OutputMode Single
        
        if ($selected) {
            if ($script:AzureClient.SetSubscription($selected.id)) {
                Set-ConfigValue -Key "Subscription" -Value $selected.id
                [System.Windows.MessageBox]::Show("Subscription set successfully!", "Success", "OK", "Information")
                Update-ConfigDialogStatus
            }
        }
    })
    
    $setTenantButton.Add_Click({
        $tenant = $tenantInput.Text.Trim()
        if ($tenant) {
            Set-ConfigValue -Key "DesiredTenant" -Value $tenant
            [System.Windows.MessageBox]::Show("Tenant ID saved!", "Success", "OK", "Information")
            Update-ConfigDialogStatus
        }
        else {
            Set-ConfigValue -Key "DesiredTenant" -Value $null
            [System.Windows.MessageBox]::Show("Tenant ID cleared!", "Success", "OK", "Information")
            Update-ConfigDialogStatus
        }
    })
    
    $closeButton.Add_Click({ $dialog.Close() })
    
    Update-ConfigDialogStatus
    [void]$dialog.ShowDialog()
}