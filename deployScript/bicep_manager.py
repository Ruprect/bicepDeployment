"""Bicep template discovery and management."""

import hashlib
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .logger import logger, LogLevel, Color


@dataclass
class BicepTemplate:
    name: str
    file: Path
    size: int
    enabled: bool
    last_modified: datetime
    last_deployment_success: Optional[bool] = None
    last_deployment_error: Optional[str] = None
    last_deployment_time: Optional[datetime] = None
    needs_redeployment: bool = False
    last_file_hash: Optional[str] = None
    last_validation_success: Optional[bool] = None
    last_validation_error: Optional[str] = None
    last_validation_time: Optional[datetime] = None


class BicepManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def _get_current_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate SHA256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except (OSError, IOError):
            return None
    
    def _determine_deployment_status(self, template_file: Path, file_settings: Optional[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
        """Determine if a template needs redeployment based on file changes and deployment history."""
        # Get current file hash for storage (but don't rely on it for comparison if missing)
        current_hash = self._get_current_file_hash(template_file)
        
        if not file_settings:
            return True, current_hash  # Never deployed, needs deployment
        
        # If last deployment failed, always needs redeployment
        last_success = file_settings.get('LastDeploymentSuccess')
        if last_success is False:
            return True, current_hash
        
        # If never deployed successfully, needs deployment (but this will show as ⚪ not 🟡)
        if last_success is None:
            return False, current_hash  # Don't mark as "changed" - it's "never deployed"
        
        # Check if we have file hash comparison available
        last_hash = file_settings.get('LastFileHash')
        if current_hash and last_hash:
            # Use hash comparison if available (most reliable)
            if current_hash != last_hash:
                return True, current_hash
            else:
                return False, current_hash
        
        # Fallback to timestamp comparison
        last_deployment_str = file_settings.get('LastDeployment')
        if last_deployment_str:
            try:
                # Parse deployment timestamp (format: "2025-09-05 09:29:07")
                last_deployment = datetime.strptime(last_deployment_str, "%Y-%m-%d %H:%M:%S")
                file_modified = datetime.fromtimestamp(template_file.stat().st_mtime)
                
                # If file was modified after last successful deployment, needs redeployment
                if file_modified > last_deployment:
                    return True, current_hash
                else:
                    return False, current_hash
            except (ValueError, OSError):
                # If we can't parse dates, assume needs redeployment to be safe
                return True, current_hash
        
        # If we have no deployment timestamp, assume needs deployment
        return True, current_hash
    
    def get_bicep_files(self) -> List[BicepTemplate]:
        """Discover and return all Bicep template files."""
        bicep_files = list(Path(".").glob("*.bicep"))
        
        # Load deployment settings to get file order and status
        settings = self.config_manager.load_deployment_settings()
        
        templates = []
        for file in bicep_files:
            # Include all files, even empty ones (they'll be handled in the display)
            
            # Find file in settings (try both with and without .bicep extension)
            # Prefer entries with deployment history over simple entries
            file_settings = None
            simple_settings = None
            
            for f in settings.file_order:
                if f.get('FileName') in [file.name, file.stem]:
                    # Check if this entry has deployment/validation history
                    has_history = any(key in f for key in ['LastDeployment', 'LastValidation', 'LastDeploymentSuccess', 'LastValidationSuccess'])
                    
                    if has_history:
                        # This entry has history, prefer it
                        file_settings = f
                        break
                    else:
                        # Simple entry, keep it as fallback
                        simple_settings = f
            
            # If we didn't find an entry with history, use the simple entry
            if file_settings is None and simple_settings is not None:
                file_settings = simple_settings
            
            # Empty files should always be disabled
            file_size = file.stat().st_size
            is_enabled = False if file_size == 0 else (file_settings.get('Enabled', True) if file_settings else True)
            
            # Determine deployment status
            needs_redeployment, current_hash = self._determine_deployment_status(file, file_settings)
            
            template = BicepTemplate(
                name=file.name,
                file=file,
                size=file_size,
                enabled=is_enabled,
                last_modified=datetime.fromtimestamp(file.stat().st_mtime),
                last_deployment_success=file_settings.get('LastDeploymentSuccess') if file_settings else None,
                last_deployment_error=file_settings.get('LastDeploymentError') if file_settings else None,
                last_deployment_time=datetime.fromisoformat(file_settings['LastDeployment']) if file_settings and file_settings.get('LastDeployment') else None,
                needs_redeployment=needs_redeployment,
                last_file_hash=current_hash,
                last_validation_success=file_settings.get('LastValidationSuccess') if file_settings else None,
                last_validation_error=file_settings.get('LastValidationError') if file_settings else None,
                last_validation_time=datetime.fromisoformat(file_settings['LastValidation']) if file_settings and file_settings.get('LastValidation') else None
            )
            
            templates.append(template)
        
        # Sort by the order in settings, then by name
        def sort_key(template):
            file_order = next(
                (i for i, f in enumerate(settings.file_order) if f.get('FileName') in [template.name, template.file.stem]),
                len(settings.file_order)
            )
            return (file_order, template.name)
        
        return sorted(templates, key=sort_key)
    
    def test_template_modified(self, template_file: Path) -> bool:
        """Check if a template has been modified since last deployment."""
        settings = self.config_manager.load_deployment_settings()
        
        # Find file in deployment history (try both with and without .bicep extension)
        file_history = next(
            (f for f in settings.file_order if f.get('FileName') in [template_file.name, template_file.stem]),
            None
        )
        
        # Use the same logic as _determine_deployment_status for consistency
        needs_redeployment, _ = self._determine_deployment_status(template_file, file_history)
        return needs_redeployment
    
    def update_deployment_history(self, template_file: Path, success: bool, error_message: Optional[str] = None) -> None:
        """Update deployment history for a template file."""
        settings = self.config_manager.load_deployment_settings()
        
        # Calculate file hash
        file_hash = None
        try:
            with open(template_file, 'rb') as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
        except (OSError, IOError):
            pass
        
        # Find or create file entry (try both with and without .bicep extension)
        # Prefer entries with deployment history over simple entries
        file_entry = None
        simple_entry = None
        
        for entry in settings.file_order:
            if entry.get('FileName') in [template_file.name, template_file.stem]:
                # Check if this entry has deployment/validation history
                has_history = any(key in entry for key in ['LastDeployment', 'LastValidation', 'LastDeploymentSuccess', 'LastValidationSuccess'])
                
                if has_history:
                    # This entry has history, prefer it
                    file_entry = entry
                    break
                else:
                    # Simple entry, keep it as fallback
                    simple_entry = entry
        
        # If we didn't find an entry with history, use the simple entry
        if file_entry is None and simple_entry is not None:
            file_entry = simple_entry
        
        if file_entry is None:
            file_entry = {'FileName': template_file.name, 'Enabled': True}
            settings.file_order.append(file_entry)
        
        # Update deployment info
        file_entry.update({
            'LastDeploymentSuccess': success,
            'LastDeployment': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'LastFileHash': file_hash
        })
        
        if error_message:
            file_entry['LastDeploymentError'] = error_message
        elif 'LastDeploymentError' in file_entry:
            del file_entry['LastDeploymentError']
        
        self.config_manager.save_deployment_settings(settings)
    
    def update_validation_history(self, template_file: Path, success: bool, error_message: Optional[str] = None) -> None:
        """Update validation history for a template file."""
        settings = self.config_manager.load_deployment_settings()
        
        # Find or create file entry (try both with and without .bicep extension)
        # Prefer entries with deployment history over simple entries
        file_entry = None
        simple_entry = None
        
        for entry in settings.file_order:
            if entry.get('FileName') in [template_file.name, template_file.stem]:
                # Check if this entry has deployment/validation history
                has_history = any(key in entry for key in ['LastDeployment', 'LastValidation', 'LastDeploymentSuccess', 'LastValidationSuccess'])
                
                if has_history:
                    # This entry has history, prefer it
                    file_entry = entry
                    break
                else:
                    # Simple entry, keep it as fallback
                    simple_entry = entry
        
        # If we didn't find an entry with history, use the simple entry
        if file_entry is None and simple_entry is not None:
            file_entry = simple_entry
        
        if file_entry is None:
            file_entry = {'FileName': template_file.name, 'Enabled': True}
            settings.file_order.append(file_entry)
        
        # Update validation info
        file_entry.update({
            'LastValidationSuccess': success,
            'LastValidation': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        if error_message:
            file_entry['LastValidationError'] = error_message
        elif 'LastValidationError' in file_entry:
            del file_entry['LastValidationError']
        
        self.config_manager.save_deployment_settings(settings)
    
    def set_template_enabled(self, template_name: str, enabled: bool) -> bool:
        """Enable or disable a template for deployment. Returns True if successful, False if blocked (e.g., empty file)."""
        # Check if file is empty
        template_file = Path(template_name)
        if template_file.exists() and template_file.stat().st_size == 0 and enabled:
            # Cannot enable empty files
            from .logger import logger, LogLevel, Color
            logger.log(f"Cannot enable empty file: {template_name}", LogLevel.WARN, Color.YELLOW)
            return False
            
        settings = self.config_manager.load_deployment_settings()
        
        # Find or create file entry (try both with and without .bicep extension)
        # Prefer entries with deployment history over simple entries
        template_stem = Path(template_name).stem
        file_entry = None
        simple_entry = None
        
        for entry in settings.file_order:
            if entry.get('FileName') in [template_name, template_stem]:
                # Check if this entry has deployment/validation history
                has_history = any(key in entry for key in ['LastDeployment', 'LastValidation', 'LastDeploymentSuccess', 'LastValidationSuccess'])
                
                if has_history:
                    # This entry has history, prefer it
                    file_entry = entry
                    break
                else:
                    # Simple entry, keep it as fallback
                    simple_entry = entry
        
        # If we didn't find an entry with history, use the simple entry
        if file_entry is None and simple_entry is not None:
            file_entry = simple_entry
        
        if file_entry is None:
            # Create new entry only if it doesn't exist anywhere in file_order
            # This should be rare as files are usually already in the settings
            file_entry = {'FileName': template_name, 'Enabled': enabled}
            settings.file_order.append(file_entry)
        else:
            # Preserve all existing fields, only update the Enabled status
            file_entry['Enabled'] = enabled
        
        self.config_manager.save_deployment_settings(settings)
        return True
    
    def reorder_templates(self, new_order: List[str]) -> None:
        """Reorder templates according to the new order list."""
        settings = self.config_manager.load_deployment_settings()
        
        # Create new file order based on the provided order
        new_file_order = []
        
        # First, add files in the new order
        for filename in new_order:
            existing_entry = next(
                (entry for entry in settings.file_order if entry.get('FileName') == filename),
                None
            )
            
            if existing_entry:
                new_file_order.append(existing_entry)
            else:
                new_file_order.append({'FileName': filename, 'Enabled': True})
        
        # Add any remaining files that weren't in the new order
        for entry in settings.file_order:
            if entry.get('FileName') not in new_order:
                new_file_order.append(entry)
        
        settings.file_order = new_file_order
        self.config_manager.save_deployment_settings(settings)
        
        logger.log(f"Template order updated with {len(new_order)} templates", LogLevel.SUCCESS, Color.GREEN)
    
    def refresh_file_list(self) -> int:
        """Refresh the file list and return the count of discovered templates."""
        templates = self.get_bicep_files()
        
        # Update settings to include any new files discovered
        settings = self.config_manager.load_deployment_settings()
        
        existing_files = {entry.get('FileName') for entry in settings.file_order}
        new_files = []
        
        for template in templates:
            if template.name not in existing_files:
                new_files.append({'FileName': template.name, 'Enabled': True})
        
        if new_files:
            settings.file_order.extend(new_files)
            self.config_manager.save_deployment_settings(settings)
            logger.log(f"Discovered {len(new_files)} new template(s)", LogLevel.INFO, Color.CYAN)
        
        return len(templates)