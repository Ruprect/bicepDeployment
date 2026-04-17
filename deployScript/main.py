"""Main entry point for the Python deployment script."""

import sys
import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from .logger import logger, LogLevel, Color
from .config import ConfigManager
from .azure_client import AzureClient
from .bicep_manager import BicepManager
from .deployment import DeploymentManager
from .menu import MenuSystem
from .exporter import ResourceExporter
from .workflow_mappings import WorkflowMappings
from .header_generator import _load_params


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
        self.exporter = ResourceExporter(self.azure_client, self.config_manager)

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
                    if not templates:
                        logger.log("No bicep files found. Add .bicep files to deploy.", LogLevel.WARN, Color.YELLOW)
                        input("Press Enter to continue...")
                    else:
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

                elif choice == "E":
                    self._handle_export_resources()

                elif choice.isdigit():
                    self._handle_deploy_individual(templates, int(choice))

                elif '-' in choice or ',' in choice:
                    # Handle range or list input (e.g., "1-3,5,10-15")
                    self._handle_deploy_range(templates, choice)

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
        selected_file = self.menu_system.show_parameter_file_menu(parameter_files, self.selected_parameter_file)
        
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

    def _resolve_workflow_mapping_for_resource(
        self,
        resource,
        wm: WorkflowMappings,
        workflow_names: dict,
    ) -> None:
        """
        If the resource is a Logic App with no existing mapping, show the picklist
        and save the result. Updates parameters.local.json and wm in-place.
        """
        if 'Microsoft.Logic/workflows' not in resource.resource_type:
            return
        if wm.find_by_azure_name(resource.name):
            return  # already mapped

        result = self.menu_system.show_workflow_mapping_picklist(resource.name, workflow_names)
        if result is None:
            return  # user skipped

        key, is_new = result

        if is_new:
            filename = f"workflows-{resource.name}"
        else:
            filename = self._find_bicep_filename_for_key(key) or f"workflows-{resource.name}"

        wm.add(resource.name, key, filename)
        wm.save()

        self._upsert_workflow_name_in_params(key, resource.name)
        workflow_names[key] = resource.name  # keep in-memory dict in sync

    def _find_bicep_filename_for_key(self, workflow_key: str) -> Optional[str]:
        """Scan bicep/ folder for a file referencing workflowNames.<key>. Returns stem or None."""
        bicep_dir = Path("bicep")
        if not bicep_dir.is_dir():
            return None
        pattern = re.compile(rf'\bworkflowNames\.{re.escape(workflow_key)}\b')
        for f in bicep_dir.glob("*.bicep"):
            try:
                if pattern.search(f.read_text(encoding='utf-8')):
                    return f.stem
            except OSError:
                pass
        return None

    def _upsert_workflow_name_in_params(self, key: str, azure_name: str) -> None:
        """Update workflowNames.<key> = azure_name in parameters.local.json."""
        params_file = Path("parameters.local.json")
        if not params_file.exists():
            return
        try:
            data = json.loads(params_file.read_text(encoding='utf-8'))
            wn = data.setdefault('parameters', {}).setdefault('workflowNames', {})
            if 'value' not in wn:
                wn['value'] = {}
            wn['value'][key] = azure_name
            params_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        except (json.JSONDecodeError, OSError) as e:
            logger.log(f"Could not update parameters.local.json: {e}", LogLevel.WARN, Color.YELLOW)

    def _check_logic_app_name_conflict(
        self,
        template,
        mode: str,
        rg: str,
        wm: WorkflowMappings,
    ) -> str:
        """
        For Incremental deployments of Logic App bicep files:
        check if the expected resource name differs from an existing one in Azure.

        Returns: 'proceed' | 'skip' | 'use-exported'
        """
        if mode == 'Complete':
            return 'proceed'

        entry = wm.find_by_filename(template.file.stem)
        if not entry:
            return 'proceed'

        params_file = Path("parameters.local.json")
        if not params_file.exists():
            return 'proceed'

        try:
            params = _load_params(params_file)
            environment = params.get('environment', '')
            project_suffix = params.get('projectSuffix', '')
            workflow_names = params.get('workflowNames', {})
            workflow_value = workflow_names.get(entry.workflow_key, '')
            expected_name = f"la-{environment}-{project_suffix}{workflow_value}"
        except (KeyError, OSError):
            return 'proceed'

        existing = self.azure_client.list_resource_group_resources(rg)
        existing_names = {r.name for r in existing}

        if expected_name in existing_names:
            return 'proceed'  # resource exists with correct name

        if entry.azure_name not in existing_names:
            return 'proceed'  # fresh RG — no conflict

        # Conflict: old name exists, new name doesn't
        print()
        logger.log(
            f"⚠  Resource '{entry.azure_name}' exists but template will create '{expected_name}'",
            LogLevel.WARN, Color.YELLOW,
        )
        logger.log("   This creates a NEW resource rather than updating the existing one.", LogLevel.WARN, Color.YELLOW)
        print()
        print("  [S] Skip this file")
        print("  [U] Use exported name for this deployment (not saved)")
        print("  [C] Continue anyway")
        print()
        choice = input("  Choice [S/U/C]: ").strip().upper()

        if choice == 'S':
            return 'skip'
        if choice == 'U':
            return 'use-exported'
        return 'proceed'

    def _deploy_with_name_override(
        self,
        template,
        mode: str,
        rg: str,
        wm: WorkflowMappings,
        prompt_mode: str = "prompt",
    ) -> object:
        """Deploy template with workflowNames.<key> temporarily overridden to the exported Azure name."""
        entry = wm.find_by_filename(template.file.stem)
        params_file = Path("parameters.local.json")
        tmp_params = params_file.parent / "_tmp_deploy_params.json"

        try:
            data = json.loads(params_file.read_text(encoding='utf-8'))
            wn = data.setdefault('parameters', {}).setdefault('workflowNames', {})
            wn.setdefault('value', {})[entry.workflow_key] = entry.azure_name
            tmp_params.write_text(json.dumps(data, indent=2), encoding='utf-8')

            return self.deployment_manager.deploy_bicep_template(
                template.file, mode, template.name, rg,
                str(tmp_params), prompt_mode,
                skip_validation=False,
                validation_mode=self.validation_mode,
                template_needs_redeployment=template.needs_redeployment,
            )
        finally:
            if tmp_params.exists():
                tmp_params.unlink()

    def _handle_export_resources(self):
        """Handle exporting Azure Resource Group resources as individual Bicep files."""
        # Pre-flight: login check
        if not self.azure_client.test_azure_login():
            logger.log(
                "Not logged in. Use [C] Config → [L] Login first.",
                LogLevel.WARN, Color.YELLOW
            )
            input("Press Enter to continue...")
            return

        # Pre-flight: resource group check
        rg = self.config_manager.get_resource_group()
        if not rg:
            logger.log(
                "No Resource Group configured. Set one in [C] Config first.",
                LogLevel.WARN, Color.YELLOW
            )
            input("Press Enter to continue...")
            return

        # Pre-flight: az bicep check
        if not self.exporter.check_bicep_available():
            logger.log(
                "az bicep not found. Install it with: az bicep install",
                LogLevel.ERROR, Color.RED
            )
            input("Press Enter to continue...")
            return

        # Fetch resources
        logger.log(f"Loading resources from '{rg}'...", LogLevel.INFO, Color.CYAN)
        resources = self.azure_client.list_resource_group_resources(rg)
        if not resources:
            logger.log(f"No resources found in resource group '{rg}'.", LogLevel.WARN, Color.YELLOW)
            input("Press Enter to continue...")
            return

        # Picklist
        selected = self.menu_system.show_export_picklist(resources)
        if selected is None:
            return  # User pressed Q — silent cancel
        if not selected:
            logger.log("Nothing selected.", LogLevel.INFO, Color.YELLOW)
            input("Press Enter to continue...")
            return

        # Build output directory
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_dir = Path("exported") / timestamp

        # Load mappings and parameter names for pre-pass
        wm = WorkflowMappings().load()
        params_file = Path("parameters.local.json")
        workflow_names = {}
        if params_file.exists():
            try:
                data = json.loads(params_file.read_text(encoding='utf-8'))
                workflow_names = data.get('parameters', {}).get('workflowNames', {}).get('value', {})
            except (json.JSONDecodeError, OSError):
                pass

        # Pre-pass: resolve mappings for all Logic Apps before starting spinner
        for resource in selected:
            self._resolve_workflow_mapping_for_resource(resource, wm, workflow_names)

        # Export (with spinner)
        success, total = logger.show_progress_spinner(
            f"Exporting {len(selected)} resource(s)",
            self.exporter.export_resources,
            selected,
            output_dir,
            workflow_mappings=wm,
            parameters_file=params_file,
        )

        # Summary
        print()
        if success == total:
            logger.log(
                f"Exported {success}/{total} resources to {output_dir}",
                LogLevel.SUCCESS, Color.GREEN
            )
        else:
            logger.log(
                f"Exported {success}/{total} resources to {output_dir} ({total - success} failed — see above)",
                LogLevel.WARN, Color.YELLOW
            )
        input("Press Enter to continue...")

    def _parse_template_range(self, range_input: str, max_templates: int) -> list:
        """Parse a range input like '1-3,5,10-15' and return a list of template numbers.

        Args:
            range_input: String containing template numbers and ranges (e.g., "1-3,5,10-15")
            max_templates: Maximum valid template number

        Returns:
            List of template numbers, or empty list if invalid
        """
        template_numbers = []

        try:
            # Split by comma to get individual numbers or ranges
            parts = range_input.split(',')

            for part in parts:
                part = part.strip()

                if '-' in part:
                    # Handle range (e.g., "1-3" or "10-15")
                    range_parts = part.split('-')
                    if len(range_parts) != 2:
                        logger.log(f"Invalid range format: {part}", LogLevel.ERROR, Color.RED)
                        return []

                    start = int(range_parts[0].strip())
                    end = int(range_parts[1].strip())

                    if start > end:
                        logger.log(f"Invalid range {part}: start must be <= end", LogLevel.ERROR, Color.RED)
                        return []

                    if start < 1 or end > max_templates:
                        logger.log(f"Range {part} is out of bounds (1-{max_templates})", LogLevel.ERROR, Color.RED)
                        return []

                    # Add all numbers in the range
                    template_numbers.extend(range(start, end + 1))
                else:
                    # Handle single number
                    num = int(part)
                    if num < 1 or num > max_templates:
                        logger.log(f"Template number {num} is out of bounds (1-{max_templates})", LogLevel.ERROR, Color.RED)
                        return []
                    template_numbers.append(num)

            # Remove duplicates and sort
            template_numbers = sorted(set(template_numbers))
            return template_numbers

        except ValueError as e:
            logger.log(f"Invalid input format: {e}", LogLevel.ERROR, Color.RED)
            return []
    
    def _handle_deploy_range(self, templates, range_input: str):
        """Handle deployment of multiple templates specified by range.

        Args:
            templates: List of available templates
            range_input: Range string like "1-3,5,10-15"
        """
        if not templates:
            logger.log("No templates available", LogLevel.ERROR, Color.RED)
            return

        # Parse the range input
        template_numbers = self._parse_template_range(range_input, len(templates))

        if not template_numbers:
            # Error already logged by parse method
            return

        # Filter to get only enabled templates
        selected_templates = []
        disabled_templates = []
        empty_templates = []

        for num in template_numbers:
            template = templates[num - 1]
            if template.size == 0:
                empty_templates.append(template.name)
            elif not template.enabled:
                disabled_templates.append(template.name)
            else:
                selected_templates.append((num, template))

        # Show what will be deployed
        logger.log(f"\n📋 Templates to deploy: {len(selected_templates)}", LogLevel.INFO, Color.CYAN)
        for num, template in selected_templates:
            logger.log(f"  {num}. {template.name}", LogLevel.INFO, Color.WHITE)

        # Warn about skipped templates
        if disabled_templates:
            logger.log(f"\n⚠️  Skipping {len(disabled_templates)} disabled template(s):", LogLevel.WARN, Color.YELLOW)
            for name in disabled_templates:
                logger.log(f"  - {name}", LogLevel.WARN, Color.YELLOW)

        if empty_templates:
            logger.log(f"\n⚠️  Skipping {len(empty_templates)} empty template(s):", LogLevel.WARN, Color.YELLOW)
            for name in empty_templates:
                logger.log(f"  - {name}", LogLevel.WARN, Color.YELLOW)

        if not selected_templates:
            logger.log("\nNo valid templates to deploy", LogLevel.ERROR, Color.RED)
            return

        # Ask for confirmation (Y is default)
        print()
        confirm = input(f"Deploy {len(selected_templates)} template(s)? [{Color.GREEN}Y{Color.RESET}]es / [N]o (default: Yes): ").strip().upper()
        if not confirm:  # Empty input means default (Y)
            confirm = "Y"
        if confirm != "Y":
            logger.log("Deployment cancelled", LogLevel.INFO, Color.YELLOW)
            return

        # Ask once how to handle unchanged templates (D is default)
        print()
        logger.log("How should unchanged templates be handled?", LogLevel.INFO, Color.CYAN)
        print("  [S] Skip unchanged templates")
        print(f"  [{Color.GREEN}D{Color.RESET}] Deploy all templates even if unchanged (default)")
        print("  [P] Prompt for each unchanged template")
        print()
        unchanged_choice = input(f"Choose option [S/{Color.GREEN}D{Color.RESET}/P] (default: Deploy all): ").strip().upper()

        if not unchanged_choice:  # Empty input means default (D)
            unchanged_choice = "D"

        if unchanged_choice == "S":
            prompt_mode = "skip"
            logger.log("Will skip unchanged templates", LogLevel.INFO, Color.YELLOW)
        elif unchanged_choice == "D":
            prompt_mode = "deploy"
            logger.log("Will deploy all templates", LogLevel.INFO, Color.CYAN)
        elif unchanged_choice == "P":
            prompt_mode = "prompt"
            logger.log("Will prompt for each unchanged template", LogLevel.INFO, Color.CYAN)
        else:
            # Default to deploy if invalid input
            prompt_mode = "deploy"
            logger.log("Invalid choice, defaulting to deploy all templates", LogLevel.WARN, Color.YELLOW)

        # Get deployment mode (Complete only allowed for first template)
        first_template_num = template_numbers[0]
        if first_template_num == 1:
            mode = self.deployment_manager.get_deployment_mode()
            if mode is None:
                return  # User chose to quit
        else:
            mode = "Incremental"
            logger.log("Using Incremental mode (Complete mode only available when deploying from template 1)", LogLevel.INFO, Color.YELLOW)

        # Create validation mode description
        validation_desc = ""
        if self.validation_mode == "All":
            validation_desc = "validating all templates"
        elif self.validation_mode == "Changed":
            validation_desc = "validating only changed templates"
        else:  # Skip
            validation_desc = "skipping validation"

        # Global deployment header
        logger.log(f"\n🚀 Deploying {len(selected_templates)} template(s) as {Color.CYAN}{mode}{Color.RESET}, {Color.YELLOW}{validation_desc}{Color.RESET}.\n", LogLevel.INFO, Color.WHITE)

        # Deploy each template
        successful = 0
        failed = 0
        skipped = 0

        wm = WorkflowMappings().load()

        for i, (num, template) in enumerate(selected_templates, 1):
            # Template header
            logger.log(f"{Color.CYAN}▶{Color.RESET} [{i}/{len(selected_templates)}] Template: {Color.CYAN}{template.name}{Color.RESET}", LogLevel.INFO, Color.WHITE)

            # Deploy
            conflict_action = self._check_logic_app_name_conflict(
                template, mode, self.get_effective_resource_group(), wm
            )
            if conflict_action == 'skip':
                logger.log(f"Skipped: {template.name}", LogLevel.INFO, Color.YELLOW)
                skipped += 1
                continue
            elif conflict_action == 'use-exported':
                deploy_result = self._deploy_with_name_override(
                    template, mode, self.get_effective_resource_group(), wm,
                    prompt_mode=prompt_mode
                )
            else:
                deploy_result = self.deployment_manager.deploy_bicep_template(
                    template.file,
                    mode,
                    template.name,
                    self.get_effective_resource_group(),
                    self.selected_parameter_file,
                    prompt_mode,
                    skip_validation=False,
                    validation_mode=self.validation_mode,
                    template_needs_redeployment=template.needs_redeployment
                )

            # Track results
            if deploy_result is True:
                successful += 1
            elif deploy_result == "skipped":
                skipped += 1
            else:
                failed += 1
                # Ask user if they want to continue
                logger.log(f"\n⚠️  Deployment failed for: {template.name}", LogLevel.ERROR, Color.RED)

                if i < len(selected_templates):  # Not the last template
                    print()
                    continue_choice = input("Continue with remaining templates? [Y]es / [N]o: ").upper()
                    if continue_choice != "Y":
                        logger.log("Deployment sequence stopped by user", LogLevel.INFO, Color.YELLOW)
                        break

            print()  # Add spacing between templates

        # Summary
        logger.log("=" * 80, LogLevel.INFO, Color.CYAN)
        logger.log(f"📊 Deployment Summary:", LogLevel.INFO, Color.WHITE)
        logger.log(f"  ✅ Successful: {successful}", LogLevel.SUCCESS, Color.GREEN)
        if skipped > 0:
            logger.log(f"  ⏭️  Skipped: {skipped}", LogLevel.INFO, Color.YELLOW)
        if failed > 0:
            logger.log(f"  ❌ Failed: {failed}", LogLevel.ERROR, Color.RED)
        logger.log("=" * 80, LogLevel.INFO, Color.CYAN)

        # Set deployment result for menu display
        if failed == 0:
            self.menu_system.last_deployment_result = {
                "Status": "Success",
                "Message": f"{successful} template(s) deployed successfully"
            }
        else:
            self.menu_system.last_deployment_result = {
                "Status": "Failed",
                "Message": f"{failed} failed, {successful} succeeded"
            }

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

        # Pre-flight: Logic App naming conflict check
        wm = WorkflowMappings().load()
        conflict_action = self._check_logic_app_name_conflict(
            selected_template, mode, self.get_effective_resource_group(), wm
        )
        if conflict_action == 'skip':
            logger.log(f"Skipped: {selected_template.name}", LogLevel.INFO, Color.YELLOW)
            return
        elif conflict_action == 'use-exported':
            deploy_result = self._deploy_with_name_override(
                selected_template, mode, self.get_effective_resource_group(), wm
            )
        else:
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