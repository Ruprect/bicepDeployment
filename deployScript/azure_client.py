"""Azure CLI integration and authentication management."""

import subprocess
import json
import webbrowser
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .logger import logger, LogLevel, Color


@dataclass
class AzureTenant:
    tenant_id: str
    tenant_display_name: str
    tenant_default_domain: str


@dataclass
class AzureSubscription:
    subscription_id: str
    name: str
    state: str
    tenant_id: str


@dataclass
class AzureResourceGroup:
    name: str
    location: str
    provisioning_state: str


class AzureClient:
    def __init__(self, config_manager=None):
        self.current_tenant = None
        self.current_subscription = None
        self._cli_available = None  # Cache CLI availability check
        self._az_command = None  # Cache the working az command
        self._cached_tenant_info = None  # Cache tenant information
        self._cache_timestamp = None  # When cache was last updated
        self._cache_duration = 30  # Cache duration in seconds
        self.config_manager = config_manager
        
        # Load persistent cache if config manager is available
        if self.config_manager:
            self._load_persistent_cache()
    
    def _is_cache_valid(self) -> bool:
        """Check if cached tenant info is still valid."""
        if self._cache_timestamp is None or self._cached_tenant_info is None:
            return False
        
        time_since_cache = (datetime.now() - self._cache_timestamp).total_seconds()
        return time_since_cache < self._cache_duration
    
    def _update_cache(self, tenant_info: Optional[Dict[str, Any]]) -> None:
        """Update cached tenant information."""
        self._cached_tenant_info = tenant_info
        self._cache_timestamp = datetime.now()
        self._save_persistent_cache()
    
    def invalidate_cache(self) -> None:
        """Force invalidation of cached data."""
        self._cached_tenant_info = None
        self._cache_timestamp = None
        if self.config_manager:
            self.config_manager.set_azure_cache(None, datetime.now())
    
    def _load_persistent_cache(self) -> None:
        """Load cached data from persistent storage."""
        if not self.config_manager.is_azure_cache_valid(self._cache_duration):
            return
        
        cache = self.config_manager.get_azure_cache()
        if cache.get('tenant_info'):
            self._cached_tenant_info = cache['tenant_info']
            try:
                self._cache_timestamp = datetime.fromisoformat(cache['timestamp'])
            except (ValueError, TypeError, KeyError):
                self._cache_timestamp = None
    
    def _save_persistent_cache(self) -> None:
        """Save cache data to persistent storage."""
        if self.config_manager and self._cache_timestamp:
            self.config_manager.set_azure_cache(self._cached_tenant_info, self._cache_timestamp)
    
    def is_azure_cli_available(self) -> bool:
        """Check if Azure CLI is installed and available."""
        if self._cli_available is not None:
            return self._cli_available
        
        start_time = datetime.now()
        Path("logs").mkdir(exist_ok=True)
        with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{start_time}] Starting Azure CLI detection\n")
        
        # Try different command variants for Windows
        commands_to_try = ['az', 'az.cmd', 'az.exe']
        
        for cmd in commands_to_try:
            try:
                # Log to file only to avoid console spam during startup
                Path("logs").mkdir(exist_ok=True)
                with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Trying Azure CLI command: {cmd}\n")
                result = subprocess.run(
                    [cmd, '--version'],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10
                )
                
                if result.returncode == 0:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                        f.write(f"[{end_time}] Azure CLI detection completed in {duration:.2f}s - SUCCESS with {cmd}\n")
                    
                    self._cli_available = True
                    self._az_command = cmd  # Cache the working command
                    logger.log(f"Azure CLI detected successfully using command: {cmd}", LogLevel.SUCCESS, Color.GREEN)
                    return True
                else:
                    # Log to file only, don't spam console during startup
                    with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now()}] Command '{cmd}' failed with return code: {result.returncode}\n")
                        f.write(f"[{datetime.now()}] STDOUT: {result.stdout}\n")
                        f.write(f"[{datetime.now()}] STDERR: {result.stderr}\n")
                    
            except FileNotFoundError as e:
                # Log to file only, don't spam console during startup
                with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Command '{cmd}' not found: {e}\n")
                continue
            except subprocess.TimeoutExpired as e:
                # Log to file only, don't spam console during startup
                with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Timeout when checking '{cmd}': {e}\n")
                continue
            except Exception as e:
                # Log to file only, don't spam console during startup
                with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Unexpected error checking '{cmd}': {e}\n")
                continue
        
        # If we get here, none of the commands worked
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        with open("logs/azure-cli-debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{end_time}] Azure CLI detection completed in {duration:.2f}s - FAILED\n")
        
        # Only show this error if we're actually trying to use Azure CLI (not during initial startup)
        # logger.log("None of the Azure CLI commands worked", LogLevel.ERROR, Color.RED)
        self._cli_available = False
        return False
    
    def _get_az_command(self) -> str:
        """Get the working Azure CLI command."""
        if self._az_command is None:
            # Force check if not already done
            self.is_azure_cli_available()
        return self._az_command or 'az'
    
    def test_azure_login(self) -> bool:
        """Test if Azure CLI is logged in and accessible."""
        # First check if Azure CLI is available
        if not self.is_azure_cli_available():
            return False
        
        try:
            az_cmd = self._get_az_command()
            result = subprocess.run(
                [az_cmd, 'account', 'show', '--output', 'json'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                account_info = json.loads(result.stdout)
                self.current_tenant = account_info.get('tenantId')
                self.current_subscription = account_info.get('id')
                return True
            else:
                return False
                
        except FileNotFoundError:
            logger.log("Azure CLI (az) not found. Please install Azure CLI first.", LogLevel.ERROR, Color.RED)
            return False
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.log(f"Error testing Azure CLI: {e}", LogLevel.ERROR, Color.RED)
            return False
    
    def get_current_azure_tenant(self) -> Optional[str]:
        """Get the current Azure tenant ID."""
        if not self.test_azure_login():
            return None
        return self.current_tenant
    
    def get_current_azure_tenant_info(self) -> Optional[Dict[str, Any]]:
        """Get detailed information about the current Azure tenant."""
        # Return cached result if still valid
        if self._is_cache_valid():
            return self._cached_tenant_info
        
        try:
            az_cmd = self._get_az_command()
            result = subprocess.run(
                [az_cmd, 'account', 'show', '--output', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            account_info = json.loads(result.stdout)
            
            # Get tenant details
            tenant_result = subprocess.run(
                [az_cmd, 'account', 'tenant', 'show', '--tenant-id', account_info['tenantId'], '--output', 'json'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if tenant_result.returncode == 0:
                tenant_info = json.loads(tenant_result.stdout)
                result_data = {
                    'tenantId': account_info['tenantId'],
                    'displayName': tenant_info.get('displayName', 'Unknown'),
                    'defaultDomain': tenant_info.get('defaultDomain', 'Unknown'),
                    'subscriptionId': account_info['id'],
                    'subscriptionName': account_info['name']
                }
            else:
                result_data = {
                    'tenantId': account_info['tenantId'],
                    'displayName': 'Unknown',
                    'defaultDomain': 'Unknown',
                    'subscriptionId': account_info['id'],
                    'subscriptionName': account_info['name']
                }
            
            # Cache the result
            self._update_cache(result_data)
            return result_data
                
        except FileNotFoundError:
            logger.log("Azure CLI (az) not found. Please install Azure CLI first.", LogLevel.ERROR, Color.RED)
            self._update_cache(None)
            return None
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.log(f"Error getting Azure tenant info: {e}", LogLevel.ERROR, Color.RED)
            self._update_cache(None)
            return None
    
    def invoke_azure_login(self, tenant_id: Optional[str] = None) -> bool:
        """Invoke Azure CLI login process."""
        try:
            az_cmd = self._get_az_command()
            cmd = [az_cmd, 'login']
            if tenant_id:
                cmd.extend(['--tenant', tenant_id])
                
            logger.log(f"Launching Azure login{'for tenant ' + tenant_id if tenant_id else ''}...", LogLevel.INFO, Color.CYAN)
            
            result = subprocess.run(cmd, check=False)
            
            if result.returncode == 0:
                logger.log("Azure login successful", LogLevel.SUCCESS, Color.GREEN)
                self.invalidate_cache()  # Clear cache after successful login
                return True
            else:
                logger.log("Azure login failed", LogLevel.ERROR, Color.RED)
                return False
                
        except subprocess.SubprocessError as e:
            logger.log(f"Error during Azure login: {e}", LogLevel.ERROR, Color.RED)
            return False
    
    def get_azure_subscriptions(self) -> List[AzureSubscription]:
        """Get list of available Azure subscriptions."""
        try:
            az_cmd = self._get_az_command()
            result = subprocess.run(
                [az_cmd, 'account', 'list', '--output', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            subscriptions_data = json.loads(result.stdout)
            subscriptions = []
            
            for sub in subscriptions_data:
                subscriptions.append(AzureSubscription(
                    subscription_id=sub['id'],
                    name=sub['name'],
                    state=sub['state'],
                    tenant_id=sub['tenantId']
                ))
            
            return subscriptions
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.log(f"Error getting subscriptions: {e}", LogLevel.ERROR, Color.RED)
            return []
    
    def set_subscription(self, subscription_id: str) -> bool:
        """Set the active Azure subscription."""
        try:
            az_cmd = self._get_az_command()
            result = subprocess.run(
                [az_cmd, 'account', 'set', '--subscription', subscription_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                self.current_subscription = subscription_id
                logger.log(f"Subscription set to: {subscription_id}", LogLevel.SUCCESS, Color.GREEN)
                return True
            else:
                logger.log(f"Failed to set subscription: {result.stderr}", LogLevel.ERROR, Color.RED)
                return False
                
        except subprocess.SubprocessError as e:
            logger.log(f"Error setting subscription: {e}", LogLevel.ERROR, Color.RED)
            return False
    
    def get_azure_resource_groups(self) -> List[AzureResourceGroup]:
        """Get list of resource groups in the current subscription."""
        try:
            az_cmd = self._get_az_command()
            result = subprocess.run(
                [az_cmd, 'group', 'list', '--output', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            groups_data = json.loads(result.stdout)
            groups = []
            
            for group in groups_data:
                groups.append(AzureResourceGroup(
                    name=group['name'],
                    location=group['location'],
                    provisioning_state=group['properties']['provisioningState']
                ))
            
            return sorted(groups, key=lambda x: x.name)
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.log(f"Error getting resource groups: {e}", LogLevel.ERROR, Color.RED)
            return []
    
    def validate_template(self, resource_group: str, template_file: str, parameters_file: Optional[str] = None) -> Tuple[bool, str]:
        """Validate a Bicep template."""
        try:
            az_cmd = self._get_az_command()
            cmd = [
                az_cmd, 'deployment', 'group', 'validate',
                '--resource-group', resource_group,
                '--template-file', template_file,
                '--output', 'json'  # Ensure JSON output for consistent parsing
            ]
            
            if parameters_file:
                cmd.extend(['--parameters', f'@{parameters_file}'])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,  # 30 second timeout for validation
                stdin=subprocess.DEVNULL  # Prevent waiting for user input
            )
            
            if result.returncode == 0:
                return True, "Template validation successful"
            else:
                # Combine both stderr and stdout to capture all error information
                full_error = ""
                if result.stdout:
                    full_error += f"STDOUT: {result.stdout}\n"
                if result.stderr:
                    full_error += f"STDERR: {result.stderr}\n"
                
                error_msg = full_error.strip() or "Template validation failed"
                
                # If we get the generic EOF error, try to extract parameter information
                if "EOF when reading a line" in error_msg:
                    # Look for parameter prompts in the combined output
                    lines = error_msg.split('\n')
                    for line in lines:
                        if "Please provide" in line and "value for" in line:
                            # Extract parameter name from prompt like "Please provide object value for 'bottomLine'"
                            import re
                            match = re.search(r"Please provide .+ value for '([^']+)'", line)
                            if match:
                                param_name = match.group(1)
                                error_msg = f"Missing or invalid parameter: '{param_name}'. Check parameter name casing and structure in parameters file."
                                break
                    else:
                        # If we can't extract specific parameter, show full error details
                        error_msg = f"Parameter validation failed. Full error details:\n{full_error}"
                
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Template validation timed out after 30 seconds"
        except subprocess.SubprocessError as e:
            return False, f"Error during template validation: {e}"
    
    def deploy_template(self, resource_group: str, template_file: str, parameters_file: Optional[str] = None, mode: str = "Incremental") -> Tuple[bool, str]:
        """Deploy a Bicep template."""
        try:
            # Generate deployment name with timestamp
            from datetime import datetime
            from pathlib import Path
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            template_name = Path(template_file).stem
            deployment_name = f"{template_name}-{timestamp}"
            
            az_cmd = self._get_az_command()
            cmd = [
                az_cmd, 'deployment', 'group', 'create',
                '--resource-group', resource_group,
                '--template-file', template_file,
                '--name', deployment_name,
                '--mode', mode
            ]
            
            if parameters_file:
                cmd.extend(['--parameters', f'@{parameters_file}'])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return True, f"Deployment successful (name: {deployment_name})"
            else:
                return False, result.stderr or "Deployment failed"
                
        except subprocess.SubprocessError as e:
            return False, f"Error during deployment: {e}"