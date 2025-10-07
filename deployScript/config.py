"""Configuration management for the deployment script."""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DeploymentSettings:
    selected_parameter_file: Optional[str] = None
    last_updated: Optional[str] = None
    file_order: List[Dict[str, Any]] = None
    configuration: Dict[str, Any] = None

    def __post_init__(self):
        if self.file_order is None:
            self.file_order = []
        if self.configuration is None:
            self.configuration = {}


class ConfigManager:
    def __init__(self, settings_file: str = ".deployment-settings.json"):
        self.settings_file = Path(settings_file)
        self.chrome_executable_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.chrome_user_data_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), r"Google\Chrome\User Data")
        
    def load_deployment_settings(self) -> DeploymentSettings:
        """Load deployment settings from JSON file."""
        if not self.settings_file.exists():
            return DeploymentSettings()
            
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return DeploymentSettings(
                    selected_parameter_file=data.get('SelectedParameterFile'),
                    last_updated=data.get('LastUpdated'),
                    file_order=data.get('FileOrder', []),
                    configuration=data.get('Configuration', {})
                )
        except (json.JSONDecodeError, FileNotFoundError):
            return DeploymentSettings()
    
    def save_deployment_settings(self, settings: DeploymentSettings) -> None:
        """Save deployment settings to JSON file."""
        settings.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data = {
            'SelectedParameterFile': settings.selected_parameter_file,
            'LastUpdated': settings.last_updated,
            'FileOrder': settings.file_order,
            'Configuration': settings.configuration
        }
        
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_parameter_files(self) -> List[Path]:
        """Get available parameter files."""
        local_param_file = Path("parameters.local.json")
        if not local_param_file.exists():
            self.initialize_local_parameter_file()
        
        param_files = list(Path(".").glob("parameters.*.json"))
        return sorted(param_files)
    
    def initialize_local_parameter_file(self) -> None:
        """Initialize local parameter file with default template."""
        default_parameters = {
            '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
            'contentVersion': '1.0.0.0',
            'parameters': {
                'environment': {
                    'value': 'test'
                },
                'logicAppState': {
                    'value': 'Disabled'
                },
                'workflowNames': {
                    'value': {}
                },
                'dataverse': {
                    'value': {
                        'uri': '%%URL for Dataverse%%',
                        'clientSecret': '%%Secret for Dataverse%%',
                        'clientId': '%%ClientId for Dataverse%%'
                    }
                },
                'businessCentral': {
                    'value': {
                        'environmentName': '%%BC EnvironmentName%%',
                        'countries': [
                            {
                                'name': 'norway',
                                'companyId': '%%CompanyId%%'
                            },
                            {
                                'name': 'sweden',
                                'companyId': '%%CompanyId%%'
                            }
                        ],
                        'apiCategories': {}
                    }
                }
            }
        }
        
        with open("parameters.local.json", 'w', encoding='utf-8') as f:
            json.dump(default_parameters, f, indent=2, ensure_ascii=False)
    
    def get_desired_tenant(self) -> Optional[str]:
        """Get the desired tenant ID from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('DesiredTenant')
    
    def set_desired_tenant(self, tenant_id: str) -> None:
        """Set the desired tenant ID in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['DesiredTenant'] = tenant_id
        self.save_deployment_settings(settings)
    
    def get_chrome_profile(self) -> Optional[str]:
        """Get the Chrome profile from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('ChromeProfile')
    
    def set_chrome_profile(self, profile: str) -> None:
        """Set the Chrome profile in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['ChromeProfile'] = profile
        self.save_deployment_settings(settings)
    
    def get_subscription(self) -> Optional[str]:
        """Get the subscription from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('Subscription')
    
    def set_subscription(self, subscription: str) -> None:
        """Set the subscription in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['Subscription'] = subscription
        self.save_deployment_settings(settings)
    
    def get_resource_group(self) -> Optional[str]:
        """Get the resource group from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('ResourceGroup')
    
    def set_resource_group(self, resource_group: str) -> None:
        """Set the resource group in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['ResourceGroup'] = resource_group
        self.save_deployment_settings(settings)
    
    def get_console_width(self) -> int:
        """Get the console width from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('ConsoleWidth', 75)  # Default to 75 if missing
    
    def get_azure_cache(self) -> Dict[str, Any]:
        """Get cached Azure information."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('azure_cache', {})
    
    def set_azure_cache(self, tenant_info: Optional[Dict[str, Any]], timestamp: datetime) -> None:
        """Save Azure cache information to deployment settings."""
        settings = self.load_deployment_settings()
        settings.configuration['azure_cache'] = {
            'tenant_info': tenant_info,
            'timestamp': timestamp.isoformat(),
            'cli_available': True if tenant_info else False
        }
        self.save_deployment_settings(settings)
    
    def is_azure_cache_valid(self, cache_duration: int = 30) -> bool:
        """Check if cached Azure data is still valid."""
        cache = self.get_azure_cache()
        if not cache or 'timestamp' not in cache:
            return False
        
        try:
            cache_time = datetime.fromisoformat(cache['timestamp'])
            time_since_cache = (datetime.now() - cache_time).total_seconds()
            return time_since_cache < cache_duration
        except (ValueError, TypeError):
            return False
    
    def set_console_width(self, width: int) -> None:
        """Set the console width in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['ConsoleWidth'] = width
        self.save_deployment_settings(settings)
    
    def get_validation_mode(self) -> str:
        """Get the validation mode from settings."""
        settings = self.load_deployment_settings()
        return settings.configuration.get('ValidationMode', 'All')  # Default to 'All' if missing
    
    def set_validation_mode(self, validation_mode: str) -> None:
        """Set the validation mode in settings."""
        settings = self.load_deployment_settings()
        settings.configuration['ValidationMode'] = validation_mode
        self.save_deployment_settings(settings)