"""Main entry point for the Python deployment script."""

import sys
import argparse
from pathlib import Path

from .logger import logger, LogLevel, Color
from .config import ConfigManager
from .azure_client import AzureClient
from .bicep_manager import BicepManager
from .deployment import DeploymentManager
from .menu import MenuSystem


class DeployScript:
    def __init__(self, resource_group: str = "MyResourceGroup"):
        self.resource_group = resource_group
        
        # Initialize components
        self.config_manager = ConfigManager()
        self.azure_client = AzureClient(self.config_manager)
        self.bicep_manager = BicepManager(self.config_manager)
        self.deployment_manager = DeploymentManager(
            self.azure_client, 
            self.bicep_manager, 
            self.config_manager
        )
        self.menu_system = MenuSystem(self.azure_client, self.config_manager)
        
        # Runtime state
        self.selected_parameter_file = None
        self.validation_mode = self.config_manager.get_validation_mode()  # Load from config
        
    def initialize(self):
        """Initialize the deployment script."""
        try:
            # Start logging
            logger.start_deployment_log(self.get_effective_resource_group())
            
            # Load settings
            settings = self.config_manager.load_deployment_settings()
            if settings.selected_parameter_file:
                param_file = Path(settings.selected_parameter_file)
                if param_file.exists():
                    self.selected_parameter_file = param_file
            
            # Check Azure login
            if not self.azure_client.test_azure_login():
                logger.log("Not logged in to Azure. Please use 'C' option to configure Azure access.", LogLevel.WARN, Color.YELLOW)
                
        except Exception as e:
            logger.log(f"Initialization error: {e}", LogLevel.ERROR, Color.RED)
            # Continue running so user can still access configuration menu
    
    def get_effective_resource_group(self) -> str:
        """Get the effective resource group (from config or default)."""
        configured_rg = self.config_manager.get_resource_group()
        return configured_rg if configured_rg else self.resource_group
    
    def run(self):
        """Run the main deployment script loop."""
        self.initialize()
        
        logger.log("Python deployment script started", LogLevel.START, Color.GREEN)
        
        while True:
            try:
                # Get current templates
                templates = self.bicep_manager.get_bicep_files()
                
                # Show main menu
                self.menu_system.show_main_menu(
                    templates, 
                    self.get_effective_resource_group(),
                    self.selected_parameter_file,
                    self.validation_mode
                )
                
                # Get user choice
                choice = input("Enter your choice: ").upper()
                
                if choice == "Q":
                    logger.log("Goodbye!", LogLevel.INFO, Color.GREEN)
                    break
                    
                elif choice == "A":
                    self._handle_deploy_all(templates)
                    
                elif choice == "V":
                    self._handle_toggle_validation_mode()
                    
                elif choice == "O":
                    self._handle_reorder_templates(templates)
                    
                elif choice == "P":
                    self._handle_select_parameter_file()
                    
                elif choice == "R":
                    self._handle_refresh_files()
                    
                elif choice == "C":
                    self.menu_system.show_configuration_menu()
                    
                elif choice.isdigit():
                    self._handle_deploy_individual(templates, int(choice))
                    
                else:
                    logger.log("Invalid choice. Please try again.", LogLevel.ERROR, Color.RED)
                    # Continue without waiting
                    
            except KeyboardInterrupt:
                logger.log("\nScript interrupted by user", LogLevel.INFO, Color.YELLOW)
                break
            except Exception as e:
                logger.log(f"Unexpected error: {str(e)}", LogLevel.ERROR, Color.RED)
                
                # Provide helpful guidance for common errors
                if "Den angivne fil blev ikke fundet" in str(e) or "The system cannot find the file specified" in str(e):
                    logger.log("This error usually means Azure CLI is not installed or not in PATH.", LogLevel.INFO, Color.YELLOW)
                    logger.log("Please install Azure CLI from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli", LogLevel.INFO, Color.CYAN)
                    logger.log("After installation, restart your terminal and try again.", LogLevel.INFO, Color.CYAN)
                
                # Continue without waiting
    
    def _handle_deploy_all(self, templates):
        """Handle deployment of all enabled templates."""
        successful, failed = self.deployment_manager.deploy_all_templates(
            templates,
            self.get_effective_resource_group(),
            self.selected_parameter_file,
            self.validation_mode
        )
        
        if failed == 0:
            self.menu_system.last_deployment_result = {
                "Status": "Success",
                "Message": f"All templates deployed successfully ({successful} templates)"
            }
        else:
            self.menu_system.last_deployment_result = {
                "Status": "Failed", 
                "Message": f"{failed} template(s) failed, {successful} succeeded"
            }
        
        # Continue without waiting
    
    def _handle_toggle_validation_mode(self):
        """Toggle between validation modes: All -> Changed -> Skip -> All."""
        if self.validation_mode == "All":
            self.validation_mode = "Changed"
        elif self.validation_mode == "Changed":
            self.validation_mode = "Skip"
        else:  # Skip
            self.validation_mode = "All"
        
        # Save to config
        self.config_manager.set_validation_mode(self.validation_mode)
        
        # Show brief feedback
        from .logger import logger, LogLevel, Color
        logger.log(f"Validation mode changed to: {self.validation_mode}", LogLevel.INFO, Color.CYAN)
    
    def _handle_reorder_templates(self, templates):
        """Handle template reordering and enabling/disabling."""
        if not templates:
            logger.log("No templates available for reordering", LogLevel.WARN, Color.YELLOW)
            # Continue without waiting
            return
        
        new_order = self.menu_system.show_reorder_menu(templates)
        
        # Update enabled/disabled status
        for template in templates:
            success = self.bicep_manager.set_template_enabled(template.name, template.enabled)
            # If setting enabled state failed (e.g., trying to enable empty file), 
            # the template object will retain its old state which is correct
        
        # Update order
        if new_order and new_order != [t.name for t in self.bicep_manager.get_bicep_files()]:
            self.bicep_manager.reorder_templates(new_order)
    
    def _handle_select_parameter_file(self):
        """Handle parameter file selection."""
        parameter_files = self.config_manager.get_parameter_files()
        selected_file = self.menu_system.show_parameter_file_menu(parameter_files)
        
        if selected_file:
            self.selected_parameter_file = selected_file
            # Save selection to settings
            settings = self.config_manager.load_deployment_settings()
            settings.selected_parameter_file = str(selected_file)
            self.config_manager.save_deployment_settings(settings)
        else:
            self.selected_parameter_file = None
            # Clear selection from settings
            settings = self.config_manager.load_deployment_settings()
            settings.selected_parameter_file = None
            self.config_manager.save_deployment_settings(settings)
        
        # Continue without waiting
    
    def _handle_refresh_files(self):
        """Handle refreshing the template file list."""
        count = self.bicep_manager.refresh_file_list()
        logger.log(f"File list refreshed. Found {count} template(s).", LogLevel.INFO, Color.GREEN)
    
    def _handle_deploy_individual(self, templates, template_num):
        """Handle deployment of an individual template."""
        if not templates or template_num < 1 or template_num > len(templates):
            logger.log("Invalid template number", LogLevel.ERROR, Color.RED)
            # Continue without waiting
            return
        
        selected_template = templates[template_num - 1]
        
        if not selected_template.enabled:
            logger.log(f"Template '{selected_template.name}' is disabled. Enable it first in reorder mode (O).", LogLevel.ERROR, Color.RED)
            # Continue without waiting
            return
            
        if selected_template.size == 0:
            logger.log(f"Template '{selected_template.name}' is empty and cannot be deployed.", LogLevel.ERROR, Color.RED)
            # Continue without waiting
            return
        
        # Check for previous deployment errors
        if selected_template.last_deployment_error and not selected_template.last_deployment_success:
            logger.log("WARNING: Previous deployment failed with error:", LogLevel.WARN, Color.RED)
            logger.log("=" * 80, LogLevel.WARN, Color.RED)
            logger.log(selected_template.last_deployment_error, LogLevel.WARN, Color.YELLOW)
            logger.log("=" * 80, LogLevel.WARN, Color.RED)
            
            continue_choice = input("Do you want to continue with deployment? [Y]es / [N]o: ").upper()
            if continue_choice == "N":
                logger.log("Deployment cancelled.", LogLevel.INFO, Color.YELLOW)
                # Continue without waiting
                return
        
        # Get deployment mode (Complete only allowed for first template)
        template_index = template_num - 1
        if template_index == 0:
            mode = self.deployment_manager.get_deployment_mode()
            if mode is None:
                return  # User chose to quit
        else:
            mode = "Incremental"
            logger.log("Using Incremental mode (Complete mode only available for first template)", LogLevel.INFO, Color.YELLOW)
        
        # Create validation mode description  
        validation_desc = ""
        if self.validation_mode == "All":
            validation_desc = "validating template"
        elif self.validation_mode == "Changed":
            validation_desc = "validating only if changed"
        else:  # Skip
            validation_desc = "skipping validation"
        
        # Global deployment header
        logger.log(f"🚀 Deploying bicep template as {Color.CYAN}{mode}{Color.RESET}, {Color.YELLOW}{validation_desc}{Color.RESET}.\n", LogLevel.INFO, Color.WHITE)
        
        # Template header
        logger.log(f"{Color.CYAN}▶{Color.RESET} Template: {Color.CYAN}{selected_template.name}{Color.RESET}", LogLevel.INFO, Color.WHITE)
        
        # Deploy
        deploy_result = self.deployment_manager.deploy_bicep_template(
            selected_template.file,
            mode,
            selected_template.name,
            self.get_effective_resource_group(),
            self.selected_parameter_file,
            "prompt",
            skip_validation=False,
            validation_mode=self.validation_mode,
            template_needs_redeployment=selected_template.needs_redeployment
        )
        
        # Set deployment result for menu display
        if deploy_result is True:
            self.menu_system.last_deployment_result = {
                "Status": "Success",
                "Message": f"{selected_template.name} deployed successfully"
            }
        elif deploy_result == "skipped":
            self.menu_system.last_deployment_result = {
                "Status": "Success", 
                "Message": f"{selected_template.name} skipped (unchanged)"
            }
        else:
            self.menu_system.last_deployment_result = {
                "Status": "Failed",
                "Message": f"{selected_template.name} deployment failed"
            }
            
        # Continue without waiting


def main():
    """Main entry point for command line execution."""
    parser = argparse.ArgumentParser(description="Azure Bicep Deployment Script")
    parser.add_argument(
        "--resource-group", 
        "-r",
        default="MyResourceGroup",
        help="Azure resource group name"
    )
    
    args = parser.parse_args()
    
    try:
        script = DeployScript(args.resource_group)
        script.run()
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()