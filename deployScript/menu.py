"""Interactive menu system for the deployment script."""

import os
import shutil
import sys
from typing import List, Optional
from pathlib import Path

from .logger import logger, LogLevel, Color
from .bicep_manager import BicepTemplate
from .azure_client import AzureClient, AzureSubscription, AzureResourceGroup
from .config import ConfigManager


class MenuSystem:
    def __init__(self, azure_client: AzureClient, config_manager: ConfigManager):
        self.azure_client = azure_client
        self.config_manager = config_manager
        self.last_deployment_result = None
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _get_key(self):
        """Get a single key press (Windows and Unix compatible)."""
        if os.name == 'nt':  # Windows
            import msvcrt
            key = msvcrt.getch()
            if key == b'\xe0':  # Special key prefix on Windows
                key = msvcrt.getch()
                if key == b'H':  # Up arrow
                    return 'UP'
                elif key == b'P':  # Down arrow
                    return 'DOWN'
                elif key == b'K':  # Left arrow
                    return 'LEFT'
                elif key == b'M':  # Right arrow
                    return 'RIGHT'
            elif key == b'\r':  # Enter
                return 'ENTER'
            elif key == b'\x1b':  # Escape
                return 'ESC'
            else:
                return key.decode('utf-8', errors='ignore').upper()
        else:  # Unix/Linux
            import tty, termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                key = sys.stdin.read(1)
                if key == '\x1b':  # Escape sequence
                    key += sys.stdin.read(2)
                    if key == '\x1b[A':
                        return 'UP'
                    elif key == '\x1b[B':
                        return 'DOWN'
                    elif key == '\x1b[C':
                        return 'RIGHT'
                    elif key == '\x1b[D':
                        return 'LEFT'
                elif key == '\r' or key == '\n':
                    return 'ENTER'
                elif key == '\x1b':
                    return 'ESC'
                else:
                    return key.upper()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def _colorize_option(self, option_text: str) -> str:
        """Add color to menu option with brackets."""
        # Check if option has brackets
        if '[' in option_text and ']' in option_text:
            # Find the bracketed letter
            start = option_text.find('[')
            end = option_text.find(']')
            if start != -1 and end != -1:
                letter = option_text[start:end+1]  # Include brackets
                rest = option_text[end+1:]
                
                # Add color (cyan for brackets and letter, white for description)
                return f"{Color.CYAN}{letter}{Color.WHITE}{rest}{Color.RESET}"
        
        # For number ranges, highlight the numbers
        if '-' in option_text and option_text[0].isdigit():
            parts = option_text.split(' ', 1)
            number_part = parts[0]
            desc_part = parts[1] if len(parts) > 1 else ""
            return f"{Color.CYAN}{number_part}{Color.WHITE} {desc_part}{Color.RESET}"
        
        return option_text
    
    def _get_console_width(self) -> int:
        """Get console width from configuration, defaulting to 75 if not set."""
        return self.config_manager.get_console_width()
    
    def _get_column_widths(self) -> tuple[int, int]:
        """Calculate column widths based on console width."""
        console_width = self._get_console_width()
        if console_width >= 100:
            return 48, 40  # First column, other columns
        elif console_width >= 85:
            return 40, 35
        else:
            return 35, 30
    
    def _get_separator(self) -> str:
        """Get separator line based on console width."""
        return "=" * self._get_console_width()
    
    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI color codes to get actual text length."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def _format_menu_with_wrapping(self, options: List[str]) -> List[str]:
        """Format menu options with line wrapping based on console width."""
        console_width = self._get_console_width()
        max_line_width = console_width - 4  # Leave some margin
        
        colored_options = [self._colorize_option(option) for option in options]
        
        lines = []
        current_line = ""
        current_line_length = 0
        
        for i, colored_option in enumerate(colored_options):
            # Get actual text length without ANSI codes
            option_length = len(self._strip_ansi_codes(colored_option))
            separator = f"{Color.GRAY} | {Color.RESET}" if i > 0 else ""
            separator_length = 3 if i > 0 else 0  # " | " is 3 characters
            
            # Check if adding this option would exceed the line width
            if current_line_length + separator_length + option_length > max_line_width and current_line:
                # Start a new line
                lines.append(current_line)
                current_line = colored_option
                current_line_length = option_length
            else:
                # Add to current line
                current_line += separator + colored_option
                current_line_length += separator_length + option_length
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _get_deployment_status_indicator(self, template: BicepTemplate) -> str:
        """Get deployment status indicator for a template."""
        if template.size == 0:
            return "⚫"  # Empty file - black circle
        elif template.last_deployment_success is None:
            return "⚪"  # Never deployed
        elif template.last_deployment_success is False:
            return "🔴"  # Failed deployment
        elif template.needs_redeployment:
            return "🟡"  # File changed since last successful deployment, needs redeployment
        else:
            return "🟢"  # Successfully deployed, no changes
    
    def _get_validation_status_indicator(self, template: BicepTemplate) -> str:
        """Get validation status indicator for a template."""
        if template.size == 0:
            return "⚫"  # Empty file - black circle
        elif template.last_validation_success is None:
            return "⚪"  # Never validated
        elif template.last_validation_success is False:
            return "❌"  # Failed validation
        else:
            return "✅"  # Successful validation
    
    def _display_templates_in_columns(self, templates: List[BicepTemplate]):
        """Display templates in columns if there are many templates."""
        if len(templates) <= 20:
            # Single column for 20 or fewer templates
            for i, template in enumerate(templates, 1):
                status = "✅" if template.enabled else "❌"
                
                # Enhanced deployment status indicator
                deploy_status = self._get_deployment_status_indicator(template)
                validation_status = self._get_validation_status_indicator(template)
                
                # Handle empty files differently
                if template.size == 0:
                    # Empty file - show in yellow
                    colored_name = f"{Color.YELLOW}{template.name}{Color.RESET}"
                    print(f"  {i:2d}. {status}{deploy_status}{validation_status} {colored_name}")
                else:
                    print(f"  {i:2d}. {status}{deploy_status}{validation_status} {template.name}")
        else:
            # Multiple columns for more than 20 templates
            self._display_templates_multi_column(templates)
    
    def _display_templates_multi_column(self, templates: List[BicepTemplate]):
        """Display templates in multiple columns."""
        # Calculate number of columns based on template count
        total_templates = len(templates)
        if total_templates <= 40:
            cols = 2
        elif total_templates <= 60:
            cols = 3
        else:
            cols = 4
        
        # Calculate rows per column
        rows_per_col = (total_templates + cols - 1) // cols
        
        # Create column data
        columns = []
        for col in range(cols):
            start_idx = col * rows_per_col
            end_idx = min(start_idx + rows_per_col, total_templates)
            columns.append(templates[start_idx:end_idx])
        
        # Display columns side by side
        max_rows = max(len(col) for col in columns)
        
        for row in range(max_rows):
            line_parts = []
            
            for col_idx, column in enumerate(columns):
                if row < len(column):
                    template = column[row]
                    template_num = col_idx * rows_per_col + row + 1
                    status = "✅" if template.enabled else "❌"
                    
                    # Enhanced deployment status indicator
                    deploy_status = self._get_deployment_status_indicator(template)
                    validation_status = self._get_validation_status_indicator(template)
                    
                    # Handle empty files differently
                    if template.size == 0:
                        # Empty file - show in yellow
                        if col_idx == 0:
                            template_entry = f"  {template_num:2d}. {status}{deploy_status}{validation_status} {Color.YELLOW}{template.name}{Color.RESET}"
                        else:
                            template_entry = f"{template_num:2d}. {status}{deploy_status}{validation_status} {Color.YELLOW}{template.name}{Color.RESET}"
                    else:
                        # Format template entry - first column gets indent, others don't
                        if col_idx == 0:
                            template_entry = f"  {template_num:2d}. {status}{deploy_status}{validation_status} {template.name}"
                        else:
                            template_entry = f"{template_num:2d}. {status}{deploy_status}{validation_status} {template.name}"
                    
                    # Dynamic width for each column based on console width
                    first_col_width, other_col_width = self._get_column_widths()
                    if col_idx == 0:
                        line_parts.append(template_entry.ljust(first_col_width))  # First column with indent
                    else:
                        line_parts.append(template_entry.ljust(other_col_width))  # Other columns without indent
                else:
                    # Empty space for alignment (dynamic based on console width)
                    first_col_width, other_col_width = self._get_column_widths()
                    if col_idx == 0:
                        line_parts.append(" " * first_col_width)
                    else:
                        line_parts.append(" " * other_col_width)
            
            print("     ".join(line_parts).rstrip())
    
    def show_main_menu(self, templates: List[BicepTemplate], resource_group: str, 
                      selected_parameter_file: Optional[Path] = None, validation_mode: str = "All"):
        """Display the main menu."""
        self.clear_screen()
        
        # Header
        console_width = self._get_console_width()
        print("=" * console_width)
        title = "BICEP TEMPLATE DEPLOYMENT SCRIPT (Python Version)"
        padding = (console_width - len(title)) // 2
        print(" " * padding + title)
        print("=" * console_width)
        
        # Current configuration
        print(f"\n📁 Resource Group: {resource_group}")
        
        if selected_parameter_file:
            print(f"⚙️  Parameter File: {selected_parameter_file.name}")
        else:
            print("⚙️  Parameter File: None selected")
        
        # Azure status - quick check without full CLI detection
        print("🔧 Azure: Use 'C' to configure and check status")
        
        # Last deployment result
        if self.last_deployment_result:
            status = self.last_deployment_result['Status']
            message = self.last_deployment_result['Message']
            
            if status == "Success":
                print(f"✅ Last Result: {message}")
            else:
                print(f"❌ Last Result: {message}")
        
        # Template list
        print(f"\n📋 Available Templates ({len(templates)} found):")
        enabled_count = sum(1 for t in templates if t.enabled)
        disabled_count = len(templates) - enabled_count
        
        if templates:
            self._display_templates_in_columns(templates)
        else:
            print("  No templates found")
        
        print(f"\n📊 Status: {enabled_count} enabled, {disabled_count} disabled")
        
        # Add deployment status legend
        if templates:
            print(f"\n🔘 Legend: ✅=Enabled ❌=Disabled")
            print(f"   Deploy: 🟢=Up to date 🟡=Changed 🔴=Failed ⚪=Never deployed ⚫=Empty")
            print(f"   Validate: ✅=Passed ❌=Failed ⚪=Never validated ⚫=Empty")
        
        # Menu options
        print()
        
        # Build options menu
        options = []
        if templates:
            options.append(f"1-{len(templates)} or range Deploy template(s)")
        
        # Import Color class for validation mode colors
        from .logger import Color
        
        # Create validation mode text with colors
        if validation_mode == "All":
            validation_text = f"({Color.GREEN}[V]alidate All{Color.RESET})"
        elif validation_mode == "Changed":
            validation_text = f"({Color.YELLOW}[V]alidate Changed{Color.RESET})"
        else:  # Skip
            validation_text = f"({Color.RED}Skip [V]alidation{Color.RESET})"
        
        options.extend([
            f"[A] Deploy all {validation_text}",
            "[O] Reorder",
            "[P] Parameters", 
            "[R] Refresh",
            "[C] Config",
            "[Q] Quit"
        ])
        
        # Format menu with wrapping
        menu_lines = self._format_menu_with_wrapping(options)
        
        # Display menu with console width separators
        separator = "=" * console_width
        print(separator)
        for line in menu_lines:
            print(line)
        print(separator)

        # Show example for range input if there are templates
        if templates:
            print(f"{Color.GRAY}💡 Tip: Deploy multiple templates using ranges (e.g., 1-3,5,10-15){Color.RESET}")
    
    def show_reorder_menu(self, templates: List[BicepTemplate]) -> List[str]:
        """Show template reordering interface with arrow key navigation."""
        if not templates:
            logger.log("No templates available for reordering", LogLevel.WARN, Color.YELLOW)
            return []
        
        template_order = [t.name for t in templates]
        current_selection = 0  # Currently highlighted template
        selected_for_move = False  # Whether current template is selected for moving
        
        while True:
            self.clear_screen()
            print(self._get_separator())
            print("    TEMPLATE REORDER & ENABLE/DISABLE")
            print(self._get_separator())
            
            print("\nCurrent order and status:")
            print("Use ↑↓ to navigate, → to select/deselect for moving, ↑↓ to move selected item, ENTER to toggle enable/disable")
            print()
            
            for i, template in enumerate(templates):
                # Different indicators for highlighting vs selected for move
                if i == current_selection and selected_for_move:
                    arrow = f"{Color.MAGENTA}▶ SELECTED{Color.RESET} "
                elif i == current_selection:
                    arrow = f"{Color.CYAN}→{Color.RESET} "
                else:
                    arrow = "  "
                
                # Enable/disable status with color
                if template.enabled:
                    if template.size == 0:
                        status = f"{Color.YELLOW}❌ DISABLED (EMPTY){Color.RESET}"
                    else:
                        status = f"{Color.GREEN}✅ ENABLED{Color.RESET}"
                else:
                    if template.size == 0:
                        status = f"{Color.YELLOW}❌ DISABLED (EMPTY){Color.RESET}"
                    else:
                        status = f"{Color.RED}❌ DISABLED{Color.RESET}"
                
                # Size info
                if template.size == 0:
                    size_info = "(EMPTY)"
                else:
                    size_kb = template.size // 1024
                    size_info = f"({size_kb} KB)"
                
                # Highlight current selection or selected for move
                if i == current_selection and selected_for_move:
                    print(f"{Color.MAGENTA}{arrow}{i+1:2d}. {status} {template.name:<35} {size_info}{Color.RESET}")
                elif i == current_selection:
                    print(f"{Color.CYAN}{arrow}{i+1:2d}. {status} {template.name:<35} {size_info}{Color.RESET}")
                else:
                    print(f"{arrow}{i+1:2d}. {status} {template.name:<35} {size_info}")
            
            # Instructions
            print("\n" + self._get_separator())
            print("CONTROLS:")
            if selected_for_move:
                print("  ↑↓     Move selected template up/down")
                print("  →      Deselect template")
                print("  ENTER  Toggle enable/disable")
            else:
                print("  ↑↓     Navigate up/down")  
                print("  →      Select template for moving")
                print("  ENTER  Toggle enable/disable")
            print("  S      Save and return")
            print("  Q      Quit without saving")
            print(self._get_separator())
            
            # Get key input
            key = self._get_key()
            
            if key == 'UP':
                if selected_for_move:
                    # Move selected template up
                    if current_selection > 0:
                        # Swap current template with the one above
                        templates[current_selection], templates[current_selection - 1] = templates[current_selection - 1], templates[current_selection]
                        template_order[current_selection], template_order[current_selection - 1] = template_order[current_selection - 1], template_order[current_selection]
                        current_selection -= 1
                else:
                    # Navigate up
                    if current_selection > 0:
                        current_selection -= 1
            elif key == 'DOWN':
                if selected_for_move:
                    # Move selected template down
                    if current_selection < len(templates) - 1:
                        # Swap current template with the one below
                        templates[current_selection], templates[current_selection + 1] = templates[current_selection + 1], templates[current_selection]
                        template_order[current_selection], template_order[current_selection + 1] = template_order[current_selection + 1], template_order[current_selection]
                        current_selection += 1
                else:
                    # Navigate down
                    if current_selection < len(templates) - 1:
                        current_selection += 1
            elif key == 'RIGHT':
                # Toggle selection for moving
                selected_for_move = not selected_for_move
            elif key == 'ENTER':
                # Toggle enable/disable for current selection
                template = templates[current_selection]
                new_enabled_state = not template.enabled
                
                # Check if it's an empty file being enabled
                if template.size == 0 and new_enabled_state:
                    # Flash message at bottom of screen
                    print(f"\n{Color.YELLOW}Cannot enable empty file: {template.name}. Add content first.{Color.RESET}")
                    print("Press any key to continue...")
                    self._get_key()
                else:
                    template.enabled = new_enabled_state
            elif key in ['S', 'Q']:
                # Handle save/quit
                if key == 'S':
                    return template_order
                else:  # Q
                    return [t.name for t in templates]  # Return original order
    
    
    def show_parameter_file_menu(self, parameter_files: List[Path], current_file: Optional[Path] = None) -> Optional[Path]:
        """Show parameter file selection menu."""
        if not parameter_files:
            logger.log("No parameter files found", LogLevel.WARN, Color.YELLOW)
            return None

        self.clear_screen()
        print(self._get_separator())
        print("    PARAMETER FILE SELECTION")
        print(self._get_separator())

        if current_file:
            print(f"\n{Color.GREEN}Currently selected: {current_file.name}{Color.RESET}")

        print("\nAvailable parameter files:")
        for i, param_file in enumerate(parameter_files, 1):
            size_kb = param_file.stat().st_size // 1024
            # Highlight currently selected file in green
            if current_file and param_file.name == current_file.name:
                print(f"  {Color.GREEN}{i}. {param_file.name} ({size_kb} KB){Color.RESET}")
            else:
                print(f"  {i}. {param_file.name} ({size_kb} KB)")

        print(f"  {len(parameter_files) + 1}. None (no parameter file)")
        
        # Build options menu using the same format as main menu
        options = [f"1-{len(parameter_files) + 1} Select parameter file"]
        
        # Format menu with wrapping
        menu_lines = self._format_menu_with_wrapping(options)
        
        # Calculate the maximum line length for separator
        max_length = 0
        for line in menu_lines:
            line_length = len(self._strip_ansi_codes(line))
            max_length = max(max_length, line_length)
        
        # Display menu with dynamic separators
        print()
        separator = "=" * max_length
        print(separator)
        for line in menu_lines:
            print(line)
        print(separator)
        
        while True:
            try:
                choice_input = input(f"\nSelect parameter file (1-{len(parameter_files) + 1}, or press Enter to keep current): ").strip()

                # If empty input and there's a current selection, keep it
                if not choice_input:
                    if current_file:
                        logger.log(f"Keeping current parameter file: {current_file.name}", LogLevel.INFO, Color.CYAN)
                        return current_file
                    else:
                        logger.log("No parameter file selected", LogLevel.INFO, Color.YELLOW)
                        return None

                choice_num = int(choice_input)

                if 1 <= choice_num <= len(parameter_files):
                    selected_file = parameter_files[choice_num - 1]
                    logger.log(f"Selected parameter file: {selected_file.name}", LogLevel.SUCCESS, Color.GREEN)
                    return selected_file
                elif choice_num == len(parameter_files) + 1:
                    logger.log("No parameter file selected", LogLevel.INFO, Color.YELLOW)
                    return None
                else:
                    logger.log("Invalid choice", LogLevel.ERROR, Color.RED)

            except ValueError:
                logger.log("Please enter a valid number", LogLevel.ERROR, Color.RED)
    
    def _get_azure_status_cached(self) -> dict:
        """Get Azure status information once and cache it to avoid repeated slow CLI calls.

        Returns:
            dict: Dictionary with formatted status strings for display
        """
        cli_status = ""
        login_status = ""
        subscription_status = ""

        if not self.azure_client.is_azure_cli_available():
            cli_status = "❌ Azure CLI not installed or not in PATH"
            login_status = "🔐 Currently logged in to: Unknown"
            subscription_status = "📊 Active Subscription: None"
        else:
            cli_status = "✅ Azure CLI is available"
            tenant_info = self.azure_client.get_current_azure_tenant_info()
            if tenant_info:
                login_status = f"🔐 Currently logged in to: {tenant_info['displayName']}"
                subscription_status = f"📊 Active Subscription: {tenant_info['subscriptionName']}"
            else:
                login_status = "🔐 Currently logged in to: Unknown"
                subscription_status = "📊 Active Subscription: None"

        return {
            'cli_status': cli_status,
            'login_status': login_status,
            'subscription_status': subscription_status
        }

    def show_configuration_menu(self):
        """Show configuration management menu with arrow selection and keyboard shortcuts."""
        config_items = [
<<<<<<< HEAD
            {"name": "Set Tenant", "key": "T", "action": self._handle_tenant_selection},
            {"name": "Validate Login", "key": "V", "action": self._handle_validate_login},
            {"name": "Login", "key": "L", "action": self._handle_azure_login},
            {"name": "Set Chrome Profile", "key": "P", "action": self._handle_chrome_profile_selection},
            {"name": "Get Subscriptions", "key": "S", "action": self._handle_subscription_selection},
            {"name": "Get Resource Groups", "key": "R", "action": self._handle_resource_group_selection},
            {"name": "Console Width", "key": "W", "action": self._handle_console_width_configuration},
            {"name": "Refresh Azure Status", "key": "F", "action": self._handle_refresh_azure_status},
            {"name": "Back to Main Menu", "key": "Q", "action": None}
=======
            {"name": "[T] Set tenant", "key": "T", "action": self._handle_tenant_selection},
            {"name": "[V] Validate login", "key": "V", "action": self._handle_validate_login},
            {"name": "[L] Login to Azure", "key": "L", "action": self._handle_azure_login},
            {"name": "[P] Set Chrome profile", "key": "P", "action": self._handle_chrome_profile_selection},
            {"name": "[S] Set subscription", "key": "S", "action": self._handle_subscription_selection},
            {"name": "[R] Change Resource Group", "key": "R", "action": self._handle_resource_group_selection},
            {"name": "[W] Configure console width", "key": "W", "action": self._handle_console_width_configuration},
            {"name": "[Q] Back to main menu", "key": "Q", "action": None}
>>>>>>> 9fac298 (Enhance deployment script UX with range deployment and improved configuration menu)
        ]

        current_selection = 0

        # Show loading message before checking Azure status
        self.clear_screen()
        console_width = self._get_console_width()
        separator = "=" * console_width
        header = "AZURE CONFIGURATION"
        padding = (console_width - len(header)) // 2
        centered_header = " " * padding + header

        print(separator)
        print(centered_header)
        print(separator)
        print(f"\n{Color.CYAN}⏳ Loading Azure configuration status...{Color.RESET}")
        print(f"{Color.YELLOW}This may take a few seconds...{Color.RESET}")

        # Cache Azure status once when entering the menu to avoid repeated slow CLI calls
        azure_status_cached = self._get_azure_status_cached()

        while True:
            self.clear_screen()
            console_width = self._get_console_width()
            separator = "=" * console_width

            # Center the header
            header = "AZURE CONFIGURATION"
            padding = (console_width - len(header)) // 2
            centered_header = " " * padding + header

            print(separator)
            print(centered_header)
            print(separator)

            # Display current settings
            print("\nCurrent Settings:")
            settings = self.config_manager.load_deployment_settings()

            # Tenant
            tenant_id = self.config_manager.get_desired_tenant()
            print(f"  Tenant: {tenant_id if tenant_id else 'Not set'}")

            # Chrome Profile
            chrome_profile = self.config_manager.get_chrome_profile()
            print(f"  Chrome profile: {chrome_profile if chrome_profile else 'Default'}")

            # Subscription
            subscription = self.config_manager.get_subscription()
            print(f"  Subscription: {subscription if subscription else 'Not set'}")

            # Resource Group
            resource_group = self.config_manager.get_resource_group()
            print(f"  Resource Group: {resource_group if resource_group else 'Using default'}")

            # Console Width
            console_width_value = self.config_manager.get_console_width()
            print(f"  Console Width: {console_width_value} characters")

            # Azure CLI status - use cached version
            print("\n" + "=" * 50)
<<<<<<< HEAD
            if not self.azure_client.is_azure_cli_available():
                print("❌ Azure CLI not installed or not in PATH")
                print("🔐 Currently logged in to: Unknown")
                print("📊 Active Subscription: None")
            else:
                print("✅ Azure CLI is available")
                
                # Show cache status
                cache_valid = self.azure_client._is_cache_valid()
                cache_status = "🟢 Cached" if cache_valid else "🔄 Will refresh"
                print(f"💾 Status cache: {cache_status}")
                
                tenant_info = self.azure_client.get_current_azure_tenant_info()
                if tenant_info:
                    print(f"🔐 Currently logged in to: {tenant_info['displayName']}")
                    print(f"📊 Active Subscription: {tenant_info['subscriptionName']}")
                else:
                    print("🔐 Currently logged in to: Unknown")
                    print("📊 Active Subscription: None")
            
            # Display configuration options in main menu style
            print(f"\n{separator}")
            
            # Build options for configuration menu
            config_options = []
            for i, item in enumerate(config_items):
                option_text = f"[{item['key']}] {item['name']}"
                config_options.append(option_text)
            
            # Format menu with wrapping like main menu - this will handle coloring
            menu_lines = self._format_menu_with_wrapping(config_options)
            
            # Display menu
            for line in menu_lines:
                print(line)
            
=======
            print(azure_status_cached['cli_status'])
            print(azure_status_cached['login_status'])
            print(azure_status_cached['subscription_status'])

            # Display configuration options with arrow navigation and keyboard shortcuts
            print(f"\n{separator}")
            print("Configuration Options (↑↓ arrows + ENTER, or press key shortcut):")
            print()

            for i, item in enumerate(config_items):
                # The name already includes the [KEY] prefix, just colorize it
                name = item['name']

                # Apply colorization to the option text (cyan for [key], white for rest)
                colored_option = self._colorize_option(name)

                if i == current_selection:
                    # For selected item, add arrow and maintain the existing coloring
                    print(f"{Color.CYAN}→{Color.RESET} {colored_option}")
                else:
                    print(f"  {colored_option}")

>>>>>>> 9fac298 (Enhance deployment script UX with range deployment and improved configuration menu)
            print(f"{separator}")

            # Get key input
            key = self._get_key()

            if key == 'UP':
                if current_selection > 0:
                    current_selection -= 1
            elif key == 'DOWN':
                if current_selection < len(config_items) - 1:
                    current_selection += 1
            elif key == 'ENTER':
                selected_item = config_items[current_selection]
                if selected_item['action']:
                    selected_item['action']()
                    # Refresh Azure status cache after actions that might change it
                    if selected_item['key'] in ['V', 'L', 'S']:
                        azure_status_cached = self._get_azure_status_cached()
                else:  # Back to Main Menu
                    return
            elif key == 'Q':
                return
            else:
<<<<<<< HEAD
                # Handle direct key selection
                for item in config_items:
                    if key == item['key']:
                        if item['action']:
                            item['action']()
                        else:  # Back to Main Menu
=======
                # Check if key matches any shortcut
                for i, item in enumerate(config_items):
                    if key == item['key']:
                        current_selection = i
                        if item['action']:
                            item['action']()
                            # Refresh Azure status cache after actions that might change it
                            if item['key'] in ['V', 'L', 'S']:
                                azure_status_cached = self._get_azure_status_cached()
                        else:  # Back to Main Menu (Q)
>>>>>>> 9fac298 (Enhance deployment script UX with range deployment and improved configuration menu)
                            return
                        break
    
    def _handle_azure_login(self):
        """Handle Azure login process."""
        if not self.azure_client.is_azure_cli_available():
            logger.log("Azure CLI is not installed or not available in PATH", LogLevel.ERROR, Color.RED)
            logger.log("Please install Azure CLI first and restart your terminal", LogLevel.INFO, Color.YELLOW)
            return
            
        tenant_id = self.config_manager.get_desired_tenant()
        
        if self.azure_client.invoke_azure_login(tenant_id):
            logger.log("Login successful!", LogLevel.SUCCESS, Color.GREEN)
        else:
            logger.log("Login failed", LogLevel.ERROR, Color.RED)
    
    def _handle_validate_login(self):
        """Handle Azure login validation."""
        if not self.azure_client.is_azure_cli_available():
            logger.log("Azure CLI is not available", LogLevel.ERROR, Color.RED)
            return
            
        logger.log("Validating Azure login...", LogLevel.INFO, Color.CYAN)
        if self.azure_client.test_azure_login():
            tenant_info = self.azure_client.get_current_azure_tenant_info()
            if tenant_info:
                logger.log(f"✅ Successfully logged in to {tenant_info['displayName']}", LogLevel.SUCCESS, Color.GREEN)
                logger.log(f"   Tenant ID: {tenant_info['tenantId']}", LogLevel.INFO, Color.GRAY)
                logger.log(f"   Subscription: {tenant_info['subscriptionName']}", LogLevel.INFO, Color.GRAY)
            else:
                logger.log("✅ Logged in but could not get tenant information", LogLevel.WARN, Color.YELLOW)
        else:
            logger.log("❌ Not logged in to Azure", LogLevel.ERROR, Color.RED)
    
    def _handle_tenant_selection(self):
        """Handle tenant selection."""
        current_tenant = self.config_manager.get_desired_tenant()
        
        self.clear_screen()
        print(self._get_separator())
        print("    TENANT CONFIGURATION")
        print(self._get_separator())
        
        print(f"\nCurrent tenant: {current_tenant if current_tenant else 'Not set'}")
        print("\nCommon tenant configurations:")
        print("  - Leave blank for default tenant selection during login")
        print("  - Enter specific tenant ID (GUID format)")
        print("  - Enter tenant domain name (e.g., contoso.onmicrosoft.com)")
        print("")
        
        new_tenant = input("Enter tenant ID/domain (or press Enter to clear): ").strip()
        if new_tenant:
            self.config_manager.set_desired_tenant(new_tenant)
            logger.log(f"Tenant set to: {new_tenant}", LogLevel.SUCCESS, Color.GREEN)
        elif new_tenant == "":
            self.config_manager.set_desired_tenant(None)
            logger.log("Tenant cleared - will use default during login", LogLevel.SUCCESS, Color.GREEN)
        else:
            logger.log("No change made", LogLevel.INFO, Color.YELLOW)
    
    def _handle_chrome_profile_selection(self):
        """Handle Chrome profile selection."""
        current_profile = self.config_manager.get_chrome_profile() or "Default"
        logger.log(f"Current Chrome profile: {current_profile}", LogLevel.INFO, Color.CYAN)
        print("\nCommon Chrome profile names:")
        print("  - Default (leave blank)")
        print("  - Profile 1, Profile 2, Profile 3, etc.")
        print("  - Person 1, Person 2, Person 3, etc.")
        print("")
        
        new_profile = input("Enter Chrome profile name (or press Enter for Default): ").strip()
        if new_profile:
            self.config_manager.set_chrome_profile(new_profile)
            logger.log(f"Chrome profile set to: {new_profile}", LogLevel.SUCCESS, Color.GREEN)
        else:
            self.config_manager.set_chrome_profile("Default")
            logger.log("Chrome profile set to Default", LogLevel.SUCCESS, Color.GREEN)
    
    def _handle_subscription_selection(self):
        """Handle subscription selection."""
        # Show loading message
        self.clear_screen()
        print(self._get_separator())
        print("    SUBSCRIPTION SELECTION")
        print(self._get_separator())
<<<<<<< HEAD
        
        # Show current subscription
        current_sub = self.config_manager.get_subscription()
        if current_sub:
            print(f"\n📊 Current subscription: {current_sub}")
        else:
            print("\n📊 Current subscription: None selected")
        
        print(f"\n📋 Available subscriptions ({len(subscriptions)} found):")
        print()
        
        for i, sub in enumerate(subscriptions, 1):
            # Highlight current subscription
            if current_sub == sub.subscription_id:
                print(f"  {Color.GREEN}✓ {i:2d}. {sub.name}{Color.RESET}")
                print(f"      {Color.GRAY}📍 {sub.state} | 🏢 Tenant: {sub.tenant_id}{Color.RESET}")
                print(f"      {Color.GRAY}🆔 Subscription ID: {sub.subscription_id}{Color.RESET}")
            else:
                print(f"    {i:2d}. {sub.name}")
                print(f"       {Color.GRAY}📍 {sub.state} | 🏢 Tenant: {sub.tenant_id}{Color.RESET}")
                print(f"       {Color.GRAY}🆔 Subscription ID: {sub.subscription_id}{Color.RESET}")
            print()
        
=======
        print(f"\n{Color.CYAN}⏳ Loading subscriptions...{Color.RESET}")

        subscriptions = self.azure_client.get_azure_subscriptions()

        if not subscriptions:
            logger.log("No subscriptions found", LogLevel.ERROR, Color.RED)
            return

        # Get currently selected subscription
        current_sub = self.config_manager.get_subscription()

        self.clear_screen()
        print(self._get_separator())
        print("    SUBSCRIPTION SELECTION")
        print(self._get_separator())

        if current_sub:
            # Find the subscription name for the current ID
            current_sub_name = next((sub.name for sub in subscriptions if sub.subscription_id == current_sub), None)
            if current_sub_name:
                print(f"\n{Color.GREEN}Currently selected: {current_sub_name}{Color.RESET}")

        print("\nAvailable subscriptions:")
        for i, sub in enumerate(subscriptions, 1):
            # Mark the currently selected subscription with green color
            if current_sub and sub.subscription_id == current_sub:
                print(f"  {Color.GREEN}{i}. {sub.name} ({sub.state}){Color.RESET}")
                print(f"     {Color.GREEN}ID: {sub.subscription_id}{Color.RESET}")
            else:
                print(f"  {i}. {sub.name} ({sub.state})")
                print(f"     ID: {sub.subscription_id}")

>>>>>>> 9fac298 (Enhance deployment script UX with range deployment and improved configuration menu)
        try:
            choice_input = input(f"\nSelect subscription (1-{len(subscriptions)}, or press Enter to keep current): ").strip()

            # If empty input and there's a current selection, keep it
            if not choice_input:
                if current_sub:
                    current_sub_name = next((sub.name for sub in subscriptions if sub.subscription_id == current_sub), "Unknown")
                    logger.log(f"Keeping current subscription: {current_sub_name}", LogLevel.INFO, Color.CYAN)
                else:
                    logger.log("No subscription selected", LogLevel.WARN, Color.YELLOW)
                return

            choice = int(choice_input) - 1
            if 0 <= choice < len(subscriptions):
                selected_sub = subscriptions[choice]
                if self.azure_client.set_subscription(selected_sub.subscription_id):
                    # Set both subscription and tenant
                    self.config_manager.set_subscription(selected_sub.subscription_id)
                    self.config_manager.set_desired_tenant(selected_sub.tenant_id)
                    
                    logger.log(f"✅ Subscription set to: {selected_sub.name}", LogLevel.SUCCESS, Color.GREEN)
                    logger.log(f"✅ Tenant automatically set to: {selected_sub.tenant_id}", LogLevel.SUCCESS, Color.GREEN)
                    
                    # Invalidate Azure cache since we changed subscription/tenant
                    self.azure_client.invalidate_cache()
                else:
                    logger.log("Failed to set subscription", LogLevel.ERROR, Color.RED)
            else:
                logger.log("Invalid choice", LogLevel.ERROR, Color.RED)
        except ValueError:
            logger.log("Please enter a valid number", LogLevel.ERROR, Color.RED)
    
    def _handle_resource_group_selection(self):
        """Handle resource group selection."""
        # Show loading message
        self.clear_screen()
        print(self._get_separator())
        print("    RESOURCE GROUP SELECTION")
        print(self._get_separator())
        print(f"\n{Color.CYAN}⏳ Loading resource groups...{Color.RESET}")

        resource_groups = self.azure_client.get_azure_resource_groups()

        if not resource_groups:
            logger.log("No resource groups found", LogLevel.ERROR, Color.RED)
            return

        # Get currently selected resource group
        current_rg = self.config_manager.get_resource_group()

        self.clear_screen()
        print(self._get_separator())
        print("    RESOURCE GROUP SELECTION")
        print(self._get_separator())

        if current_rg:
            print(f"\n{Color.GREEN}Currently selected: {current_rg}{Color.RESET}")

        print("\nAvailable resource groups:")
        for i, rg in enumerate(resource_groups, 1):
            # Mark the currently selected resource group with green color
            if current_rg and rg.name == current_rg:
                print(f"  {Color.GREEN}{i}. {rg.name} ({rg.location}){Color.RESET}")
            else:
                print(f"  {i}. {rg.name} ({rg.location})")

        try:
            choice_input = input(f"\nSelect resource group (1-{len(resource_groups)}, or press Enter to keep current): ").strip()

            # If empty input and there's a current selection, keep it
            if not choice_input:
                if current_rg:
                    logger.log(f"Keeping current resource group: {current_rg}", LogLevel.INFO, Color.CYAN)
                else:
                    logger.log("No resource group selected", LogLevel.WARN, Color.YELLOW)
                return

            choice = int(choice_input) - 1
            if 0 <= choice < len(resource_groups):
                selected_rg = resource_groups[choice]
                self.config_manager.set_resource_group(selected_rg.name)
                logger.log(f"Resource group set to: {selected_rg.name}", LogLevel.SUCCESS, Color.GREEN)
            else:
                logger.log("Invalid choice", LogLevel.ERROR, Color.RED)
        except ValueError:
            logger.log("Please enter a valid number", LogLevel.ERROR, Color.RED)
    def _handle_console_width_configuration(self):
        """Handle console width configuration."""
        current_width = self.config_manager.get_console_width()
        
        self.clear_screen()
        print(self._get_separator())
        print("    CONSOLE WIDTH CONFIGURATION")
        print(self._get_separator())
        
        print(f"\nCurrent console width: {current_width} characters")
        print("\nCommon width options:")
        print("  75  - Compact layout (good for smaller terminals)")
        print("  100 - Standard layout (recommended)")
        print("  120 - Wide layout (good for larger monitors)")
        print("  150 - Extra wide layout")
        
        try:
            new_width = input(f"\nEnter new console width (50-200, current: {current_width}): ").strip()
            
            if not new_width:
                logger.log("No change made", LogLevel.INFO, Color.YELLOW)
                return
            
            width_value = int(new_width)
            
            if width_value < 50:
                logger.log("Console width must be at least 50 characters", LogLevel.ERROR, Color.RED)
            elif width_value > 200:
                logger.log("Console width cannot exceed 200 characters", LogLevel.ERROR, Color.RED)
            else:
                self.config_manager.set_console_width(width_value)
                logger.log(f"Console width set to {width_value} characters", LogLevel.SUCCESS, Color.GREEN)
                logger.log("Changes will take effect on next menu refresh", LogLevel.INFO, Color.CYAN)
                
        except ValueError:
            logger.log("Please enter a valid number", LogLevel.ERROR, Color.RED)
    
    def _handle_refresh_azure_status(self):
        """Handle refreshing Azure status cache."""
        logger.log("Refreshing Azure status cache...", LogLevel.INFO, Color.CYAN)
        self.azure_client.invalidate_cache()
        
        # Force a fresh check
        if self.azure_client.is_azure_cli_available():
            tenant_info = self.azure_client.get_current_azure_tenant_info()
            if tenant_info:
                logger.log(f"✅ Cache refreshed. Logged in to: {tenant_info['displayName']}", LogLevel.SUCCESS, Color.GREEN)
            else:
                logger.log("❌ Cache refreshed but not logged in to Azure", LogLevel.WARN, Color.YELLOW)
        else:
            logger.log("❌ Azure CLI is not available", LogLevel.ERROR, Color.RED)

