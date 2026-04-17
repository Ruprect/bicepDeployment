import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from .logger import logger, LogLevel, Color
from .workflow_mappings import WorkflowMappings, MappingEntry
from .header_generator import generate_logic_app_header, generate_keyvault_header

if TYPE_CHECKING:
    from .azure_client import AzureClient, AzureResource
    from .config import ConfigManager


class ResourceExporter:
    def __init__(self, azure_client: 'AzureClient', config_manager: 'ConfigManager'):
        self.azure_client = azure_client
        self.config_manager = config_manager

    def check_bicep_available(self) -> bool:
        """Check if az bicep is installed and available."""
        try:
            az_cmd = self.azure_client._get_az_command()
            result = subprocess.run(
                [az_cmd, 'bicep', 'version'],
                capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def export_resources(
        self,
        selected_resources: List['AzureResource'],
        output_dir: Path,
        workflow_mappings: Optional['WorkflowMappings'] = None,
        parameters_file: Optional[Path] = None,
    ) -> Tuple[int, int]:
        """Export each selected resource as a .bicep file. Creates output_dir. Returns (success, total)."""
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            logger.log(f"Failed to create output directory {output_dir}: {e}", LogLevel.ERROR, Color.RED)
            return 0, len(selected_resources)

        success = 0
        total = len(selected_resources)

        resource_group = self.config_manager.get_resource_group()

        for resource in selected_resources:
            stem = self._resolve_export_stem(resource, workflow_mappings)
            dest_bicep = output_dir / f"{stem}.bicep"

            template = self._fetch_arm_template(resource_group, resource.resource_id)
            if template is None:
                logger.log(f"❌ {resource.name}: failed to fetch ARM template", LogLevel.ERROR, Color.RED)
                continue

            tmp_path = output_dir / f"_tmp_{stem}.json"
            try:
                tmp_path.write_text(json.dumps(template, indent=2), encoding='utf-8')
            except OSError as e:
                logger.log(f"❌ {resource.name}: failed to write temp file: {e}", LogLevel.ERROR, Color.RED)
                continue

            ok, reason = self._decompile_to_bicep(tmp_path, dest_bicep)
            if ok:
                self._parameterize_location(dest_bicep)
                self._apply_standard_header(dest_bicep, workflow_mappings, parameters_file)
                logger.log(f"✅ {stem}.bicep", LogLevel.SUCCESS, Color.GREEN)
                success += 1
            else:
                # tmp_path was deleted inside _decompile_to_bicep — write fallback from in-memory template
                fallback = output_dir / f"{stem}.json"
                fallback_saved = False
                try:
                    fallback.write_text(json.dumps(template, indent=2), encoding='utf-8')
                    fallback_saved = True
                except OSError as write_err:
                    logger.log(f"   Could not save fallback JSON: {write_err}", LogLevel.ERROR, Color.RED)
                logger.log(f"❌ {resource.name}: {reason}", LogLevel.ERROR, Color.RED)
                if fallback_saved:
                    logger.log(f"   Raw ARM JSON saved as {stem}.json", LogLevel.WARN, Color.YELLOW)

        return success, total

    def _fetch_arm_template(self, resource_group: str, resource_id: str) -> Optional[dict]:
        """Fetch complete ARM template for a resource via az group export (includes apiVersion)."""
        try:
            az_cmd = self.azure_client._get_az_command()
            result = subprocess.run(
                [az_cmd, 'group', 'export', '--name', resource_group,
                 '--resource-ids', resource_id],
                capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                return None
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError):
            return None

    def _sanitize_resource_for_arm(self, resource_json: dict) -> dict:
        """Strip Azure-internal fields that cause az bicep decompile to fail or warn."""
        always_remove = {'managedBy', 'etag', 'systemData', 'changedTime', 'createdTime', 'id'}
        result = {k: v for k, v in resource_json.items() if k not in always_remove}
        if result.get('identity') is None and 'identity' in result:
            del result['identity']
        return result

    def _wrap_arm_template(self, sanitized_resource: dict) -> dict:
        """Wrap a sanitized resource in a minimal ARM deployment template envelope."""
        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [sanitized_resource]
        }

    def _decompile_to_bicep(self, tmp_json_path: Path, dest_bicep_path: Path) -> Tuple[bool, str]:
        """
        Run az bicep decompile --file <tmp_json_path>.
        Output lands at tmp_json_path.with_suffix('.bicep') — no --outfile flag.
        On success: move produced .bicep to dest_bicep_path.
        Always deletes tmp_json_path. Only deletes produced .bicep if move did not succeed.
        """
        produced_bicep = tmp_json_path.with_suffix('.bicep')
        move_succeeded = False
        try:
            az_cmd = self.azure_client._get_az_command()
            result = subprocess.run(
                [az_cmd, 'bicep', 'decompile', '--file', str(tmp_json_path)],
                capture_output=True, text=True, check=False
            )
            failed = result.returncode != 0
            warned = not failed and (
                'Decompilation failed' in result.stderr
                or 'Could not decompile' in result.stderr
            )

            if failed or warned:
                reason = (result.stderr or result.stdout).strip()
                return False, reason or "decompile failed with no output"

            shutil.move(str(produced_bicep), str(dest_bicep_path))
            move_succeeded = True
            return True, ""

        except (subprocess.SubprocessError, OSError) as e:
            return False, str(e)
        finally:
            try:
                if tmp_json_path.exists():
                    tmp_json_path.unlink()
            except OSError:
                pass
            if not move_succeeded:
                try:
                    if produced_bicep.exists():
                        produced_bicep.unlink()
                except OSError:
                    pass

    def _parameterize_location(self, bicep_path: Path) -> None:
        """Replace hardcoded location strings with resourceGroup().location."""
        try:
            text = bicep_path.read_text(encoding='utf-8')
            updated = re.sub(
                r"((?:param\s+location\s+string\s*=\s*|^\s*location:\s*))'[^']*'",
                r"\1resourceGroup().location",
                text,
                flags=re.MULTILINE
            )
            if updated != text:
                bicep_path.write_text(updated, encoding='utf-8')
        except OSError:
            pass

    def _resolve_export_stem(self, resource: 'AzureResource', workflow_mappings: Optional['WorkflowMappings']) -> str:
        """Return the output filename stem for a resource, using mapping if available."""
        if workflow_mappings and 'Microsoft.Logic/workflows' in resource.resource_type:
            entry = workflow_mappings.find_by_azure_name(resource.name)
            if entry:
                return entry.filename
        return self._make_output_filename(resource.resource_type, resource.name)

    def _apply_standard_header(
        self,
        bicep_path: Path,
        workflow_mappings: Optional['WorkflowMappings'],
        parameters_file: Optional[Path],
    ) -> None:
        """Apply standard param/var header using parameters.local.json."""
        if parameters_file is None or not parameters_file.exists():
            return
        try:
            text = bicep_path.read_text(encoding='utf-8')

            if 'Microsoft.Logic/workflows' in text:
                # Strip only the generated name param and logicAppState (both regenerated by header)
                body = re.sub(r'^param workflows_\w+ string\n?', '', text, flags=re.MULTILINE)
                body = re.sub(r'^param logicAppState string[^\n]*\n?', '', body, flags=re.MULTILINE)
                workflow_key = None
                if workflow_mappings:
                    stem = bicep_path.stem
                    entry = workflow_mappings.find_by_filename(stem)
                    if entry:
                        workflow_key = entry.workflow_key
                # Replace hardcoded state and resource name with parameter/var references
                body = re.sub(r"state:\s*'[^']+'", 'state: logicAppState', body)
                body = re.sub(r'\bname:\s*workflows_\w+\b', 'name: nameOfLogicApp', body)
                header = generate_logic_app_header(body, parameters_file, workflow_key)

            elif 'Microsoft.KeyVault/vaults' in text:
                body = re.sub(r'^param vaults_\w+ string\n?', '', text, flags=re.MULTILINE)
                body = re.sub(r'\bname:\s*vaults_\w+\b', 'name: nameOfKeyVault', body)
                header = generate_keyvault_header(body, parameters_file)

            else:
                return  # unknown resource type, leave as-is

            bicep_path.write_text(header + body.lstrip('\n'), encoding='utf-8')
        except OSError:
            pass

    def _make_output_filename(self, resource_type: str, name: str) -> str:
        """'Microsoft.Storage/storageAccounts' + 'myaccount' -> 'storageaccounts-myaccount'"""
        type_slug = resource_type.split('/')[-1].lower()
        return f"{type_slug}-{name}"
