"""Core deployment logic and orchestration."""

import time
from typing import List, Optional, Tuple
from pathlib import Path

from .logger import logger, LogLevel, Color
from .azure_client import AzureClient
from .bicep_manager import BicepTemplate, BicepManager
from .config import ConfigManager


class DeploymentManager:
    def __init__(self, azure_client: AzureClient, bicep_manager: BicepManager, config_manager: ConfigManager):
        self.azure_client = azure_client
        self.bicep_manager = bicep_manager
        self.config_manager = config_manager
        self.skip_unchanged_global = "prompt"
    
    def confirm_deploy_unchanged(self, template_name: str) -> str:
        """Ask user what to do with unchanged templates."""
        if self.skip_unchanged_global != "prompt":
            return self.skip_unchanged_global
        
        logger.log(f"Template '{template_name}' has not changed since last deployment.", LogLevel.INFO, Color.YELLOW)
        
        while True:
            choice = input("Deploy anyway? [Y]es / [N]o / [A]lways skip / A[l]ways deploy: ").upper()
            
            if choice in ["", "Y"]:
                return "deploy"
            elif choice == "N":
                return "skip"
            elif choice == "A":
                self.skip_unchanged_global = "skip"
                return "skip"
            elif choice == "L":
                self.skip_unchanged_global = "deploy"
                return "deploy"
            else:
                logger.log("Invalid choice. Please enter Y, N, A, or L.", LogLevel.ERROR, Color.RED)
    
    def get_deployment_mode(self) -> Optional[str]:
        """Get deployment mode from user."""
        from .menu import MenuSystem
        from .logger import Color
        
        # Get console width for separator (same as main menu)
        import shutil
        console_width = shutil.get_terminal_size().columns
        separator = "=" * console_width
        
        # Format options like main menu
        options = [
            "[I] Incremental (default) - Only deploy changes",
            "[C] Complete - Remove resources not in template (CAUTION)",
            "[Q] Quit - Return to main menu"
        ]
        
        # Color the options like main menu
        colored_options = [
            f"{Color.CYAN}[I]{Color.WHITE} Incremental (default) - Only deploy changes{Color.RESET}",
            f"{Color.CYAN}[C]{Color.WHITE} Complete - Remove resources not in template {Color.RED}(CAUTION){Color.RESET}",
            f"{Color.CYAN}[Q]{Color.WHITE} Quit - Return to main menu{Color.RESET}"
        ]
        
        # Try to fit on one line with pipe separators (like main menu)
        single_line = f"{Color.GRAY} | {Color.RESET}".join(colored_options)
        
        # Simple length check (rough estimate)
        if len("".join(options)) + 6 <= console_width - 4:  # Account for separators
            menu_lines = [single_line]
        else:
            menu_lines = colored_options
        
        # Display the menu
        print(separator)
        for line in menu_lines:
            print(line)
        print(separator)
        
        while True:
            choice = input("Choose deployment mode [I/C/Q]: ").upper()
            
            if choice in ["", "I"]:
                return "Incremental"
            elif choice == "C":
                logger.log("WARNING: Complete mode will remove resources not defined in the template!", LogLevel.WARN, Color.RED)
                confirm = input("Are you sure? [y/N]: ").upper()
                if confirm == "Y":
                    return "Complete"
                else:
                    logger.log("Cancelled Complete mode selection", LogLevel.INFO, Color.YELLOW)
                    continue
            elif choice == "Q":
                return None
            else:
                logger.log("Invalid choice. Please enter I, C, or Q.", LogLevel.ERROR, Color.RED)
    
    def deploy_bicep_template(self, template_file: Path, mode: str, template_name: str, 
                            resource_group: str, parameters_file: Optional[Path] = None,
                            skip_unchanged: str = "prompt", skip_validation: bool = False,
                            validation_mode: str = "All", template_needs_redeployment: bool = True) -> str:
        """Deploy a single Bicep template."""
        try:
            # Check if file is empty
            if template_file.stat().st_size == 0:
                error_msg = f"Cannot deploy empty template file: {template_name}"
                logger.log(error_msg, LogLevel.ERROR, Color.RED)
                self.bicep_manager.update_deployment_history(template_file, False, error_msg)
                return False
            
            # Check if template has changed
            template_changed = self.bicep_manager.test_template_modified(template_file)
            if not template_changed:
                action = self.confirm_deploy_unchanged(template_name) if skip_unchanged == "prompt" else skip_unchanged
                
                if action == "skip":
                    logger.log(f"  {Color.YELLOW}⏭️ Skipped {template_name} (unchanged){Color.RESET}", LogLevel.INFO, Color.WHITE)
                    return "skipped"
            
            # Determine if validation should run based on validation mode
            should_validate = False
            validation_reason = ""
            
            if skip_validation:
                # If explicitly told to skip validation (e.g., from bulk deployment)
                should_validate = False
                validation_reason = "bulk validation completed"
            elif validation_mode == "All":
                should_validate = True
                validation_reason = "validate all"
            elif validation_mode == "Changed":
                should_validate = template_needs_redeployment
                validation_reason = "validate changed only" if should_validate else "unchanged, skip validation"
            else:  # Skip validation mode
                should_validate = False
                validation_reason = "skip validation mode"
            
            # No startup message needed - will be handled by spinner and success/failure messages
            
            # Run validation if needed
            if should_validate:
                
                def validate():
                    return self.azure_client.validate_template(
                        resource_group, 
                        str(template_file), 
                        str(parameters_file) if parameters_file else None
                    )
                
                is_valid, validation_message = logger.show_progress_spinner(
                    f"Validating {template_name}",
                    validate
                )
                
                if not is_valid:
                    error_msg = f"Template validation failed: {validation_message}"
                    logger.log(error_msg, LogLevel.ERROR, Color.RED)
                    self.bicep_manager.update_deployment_history(template_file, False, error_msg)
                    return False
            
            # Deploy template
            def deploy():
                return self.azure_client.deploy_template(
                    resource_group,
                    str(template_file),
                    str(parameters_file) if parameters_file else None,
                    mode
                )
            
            success, deploy_message = logger.show_progress_spinner(
                f"Deploying {template_name}",
                deploy
            )
            
            if success:
                logger.log(f"  {Color.GREEN}✅ Successfully deployed {template_name}{Color.RESET}", LogLevel.SUCCESS, Color.WHITE)
                self.bicep_manager.update_deployment_history(template_file, True)
                return True
            else:
                error_msg = f"Deployment failed: {deploy_message}"
                logger.log(f"  {Color.RED}❌ {error_msg}{Color.RESET}", LogLevel.ERROR, Color.WHITE)
                self.bicep_manager.update_deployment_history(template_file, False, error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Unexpected error during deployment: {str(e)}"
            logger.log(f"  {Color.RED}❌ {error_msg}{Color.RESET}", LogLevel.ERROR, Color.WHITE)
            self.bicep_manager.update_deployment_history(template_file, False, error_msg)
            return False
    
    def validate_all_templates(self, templates: List[BicepTemplate], resource_group: str,
                             parameters_file: Optional[Path] = None) -> Tuple[int, int]:
        """Validate all enabled templates without deploying."""
        enabled_templates = [t for t in templates if t.enabled and t.size > 0]
        
        if not enabled_templates:
            logger.log("No enabled templates found for validation", LogLevel.WARN, Color.YELLOW)
            return 0, 0
        
        logger.log("=== BULK VALIDATION ===", LogLevel.CONFIG, Color.CYAN)
        logger.log(f"Templates: {len(enabled_templates)} enabled", LogLevel.CONFIG, Color.GRAY)
        logger.log(f"Resource Group: {resource_group}", LogLevel.CONFIG, Color.GRAY)
        if parameters_file:
            logger.log(f"Parameter File: {parameters_file.name}", LogLevel.CONFIG, Color.GRAY)
        else:
            logger.log("Parameter File: None", LogLevel.CONFIG, Color.GRAY)
        
        successful_validations = 0
        failed_validations = 0
        
        for i, template in enumerate(enabled_templates, 1):
            logger.log(f"\n--- Validating Template {i}/{len(enabled_templates)}: {template.name} ---", LogLevel.INFO, Color.CYAN)
            
            try:
                def validate():
                    return self.azure_client.validate_template(
                        resource_group, 
                        str(template.file), 
                        str(parameters_file) if parameters_file else None
                    )
                
                is_valid, validation_message = logger.show_progress_spinner(
                    f"Validating {template.name}",
                    validate
                )
                
                if is_valid:
                    logger.log(f"✅ {template.name} validation successful", LogLevel.SUCCESS, Color.GREEN)
                    self.bicep_manager.update_validation_history(template.file, True)
                    successful_validations += 1
                else:
                    logger.log(f"❌ {template.name} validation failed: {validation_message}", LogLevel.ERROR, Color.RED)
                    self.bicep_manager.update_validation_history(template.file, False, validation_message)
                    failed_validations += 1
                    
            except Exception as e:
                logger.log(f"❌ {template.name} validation error: {str(e)}", LogLevel.ERROR, Color.RED)
                self.bicep_manager.update_validation_history(template.file, False, str(e))
                failed_validations += 1
        
        # Summary
        logger.log(f"\n=== VALIDATION SUMMARY ===", LogLevel.INFO, Color.CYAN)
        logger.log(f"Successful: {successful_validations}", LogLevel.SUCCESS, Color.GREEN)
        logger.log(f"Failed: {failed_validations}", LogLevel.ERROR if failed_validations > 0 else LogLevel.INFO, Color.RED if failed_validations > 0 else Color.WHITE)
        
        return successful_validations, failed_validations
    
    def deploy_all_templates(self, templates: List[BicepTemplate], resource_group: str, 
                           parameters_file: Optional[Path] = None, validation_mode: str = "All") -> Tuple[int, int]:
        """Deploy all enabled templates in sequence."""
        enabled_templates = [t for t in templates if t.enabled]
        
        if not enabled_templates:
            logger.log("No enabled templates found for deployment", LogLevel.WARN, Color.YELLOW)
            return 0, 0
        
        # Handle validation based on validation mode
        skip_individual_validation = False
        
        if validation_mode == "All":
            logger.log("\nRunning bulk validation first (Validation Mode: All)...", LogLevel.INFO, Color.CYAN)
            successful_validations, failed_validations = self.validate_all_templates(
                templates, resource_group, parameters_file
            )
            
            if failed_validations > 0:
                logger.log(f"\n⚠️  {failed_validations} template(s) failed validation!", LogLevel.WARN, Color.RED)
                continue_choice = input("Continue with deployment anyway? [y/N]: ").upper()
                if continue_choice != "Y":
                    logger.log("Deployment cancelled due to validation failures", LogLevel.INFO, Color.YELLOW)
                    return 0, 0
            else:
                logger.log(f"\n✅ All {successful_validations} templates passed validation!", LogLevel.SUCCESS, Color.GREEN)
            
            skip_individual_validation = True
            
        elif validation_mode == "Changed":
            # Filter to only changed templates
            changed_templates = [t for t in enabled_templates if t.needs_redeployment]
            if changed_templates:
                logger.log(f"\nRunning validation for {len(changed_templates)} changed template(s) (Validation Mode: Changed)...", LogLevel.INFO, Color.CYAN)
                successful_validations, failed_validations = self.validate_all_templates(
                    changed_templates, resource_group, parameters_file
                )
                
                if failed_validations > 0:
                    logger.log(f"\n⚠️  {failed_validations} changed template(s) failed validation!", LogLevel.WARN, Color.RED)
                    continue_choice = input("Continue with deployment anyway? [y/N]: ").upper()
                    if continue_choice != "Y":
                        logger.log("Deployment cancelled due to validation failures", LogLevel.INFO, Color.YELLOW)
                        return 0, 0
                else:
                    logger.log(f"\n✅ All {successful_validations} changed templates passed validation!", LogLevel.SUCCESS, Color.GREEN)
                
                skip_individual_validation = True
            else:
                logger.log("\nNo changed templates found, proceeding with deployment...", LogLevel.INFO, Color.YELLOW)
                skip_individual_validation = False
                
        else:  # Skip validation
            logger.log("Skipping validation (Validation Mode: Skip)...", LogLevel.INFO, Color.YELLOW)
            skip_individual_validation = True
        
        # Get deployment mode
        mode = self.get_deployment_mode()
        if mode is None:
            logger.log("Deployment cancelled by user", LogLevel.INFO, Color.YELLOW)
            return 0, 0
        
        # Create validation mode description
        validation_desc = ""
        if validation_mode == "All":
            validation_desc = "validating all templates"
        elif validation_mode == "Changed":
            validation_desc = "only validating changed templates"
        else:  # Skip
            validation_desc = "skipping validation"
        
        # Global deployment header
        logger.log(f"🚀 Deploying bicep templates as {Color.CYAN}{mode}{Color.RESET}, {Color.YELLOW}{validation_desc}{Color.RESET}.\n", LogLevel.INFO, Color.WHITE)
        
        # Reset skip behavior for batch deployment
        self.skip_unchanged_global = "prompt"
        
        successful_deployments = 0
        failed_deployments = 0
        
        for i, template in enumerate(enabled_templates, 1):
            logger.log(f"{Color.CYAN}▶{Color.RESET} Template {Color.YELLOW}{i}{Color.RESET}/{Color.YELLOW}{len(enabled_templates)}{Color.RESET}: {Color.CYAN}{template.name}{Color.RESET}", LogLevel.INFO, Color.WHITE)
            
            # Check for previous deployment errors
            if template.last_deployment_error and not template.last_deployment_success:
                logger.log(f"WARNING: Previous deployment failed with error:", LogLevel.WARN, Color.RED)
                logger.log("=" * 80, LogLevel.WARN, Color.RED)
                logger.log(template.last_deployment_error, LogLevel.WARN, Color.YELLOW)
                logger.log("=" * 80, LogLevel.WARN, Color.RED)
                
                continue_choice = input("Do you want to continue with deployment? [Y]es / [N]o: ").upper()
                if continue_choice == "N":
                    logger.log(f"Skipped {template.name} (user choice)", LogLevel.INFO, Color.YELLOW)
                    continue
            
            # Use Complete mode only for first template if requested
            template_mode = mode if i == 1 else "Incremental"
            if template_mode != mode and mode == "Complete":
                logger.log("Using Incremental mode (Complete mode only available for first template)", LogLevel.INFO, Color.YELLOW)
            
            # Use the skip_individual_validation flag set by validation mode logic above
            
            result = self.deploy_bicep_template(
                template.file, 
                template_mode, 
                template.name, 
                resource_group, 
                parameters_file,
                "prompt" if self.skip_unchanged_global == "prompt" else self.skip_unchanged_global,
                skip_validation=skip_individual_validation,
                validation_mode=validation_mode,
                template_needs_redeployment=template.needs_redeployment
            )
            
            if result is True:
                successful_deployments += 1
            elif result == "skipped":
                # Count skipped as successful
                successful_deployments += 1
            else:
                failed_deployments += 1
                
                # Ask if user wants to continue
                continue_choice = input("Continue with remaining templates? [Y]es / [N]o: ").upper()
                if continue_choice == "N":
                    logger.log("Batch deployment cancelled by user", LogLevel.INFO, Color.YELLOW)
                    break
        
        # Summary
        logger.log(f"\n=== DEPLOYMENT SUMMARY ===", LogLevel.INFO, Color.CYAN)
        logger.log(f"Successful: {successful_deployments}", LogLevel.SUCCESS, Color.GREEN)
        logger.log(f"Failed: {failed_deployments}", LogLevel.ERROR if failed_deployments > 0 else LogLevel.INFO, Color.RED if failed_deployments > 0 else Color.WHITE)
        
        return successful_deployments, failed_deployments