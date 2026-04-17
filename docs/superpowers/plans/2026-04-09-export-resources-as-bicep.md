# Export Azure Resources as Bicep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `[E] Export from Azure` to the main menu, letting users pick resources from a Resource Group and download each as an individual `.bicep` file into a timestamped subfolder.

**Architecture:** Four-file change — new `AzureResource` dataclass and two CLI-wrapper methods in `azure_client.py`; new `ResourceExporter` class in `exporter.py` that owns all export orchestration; a new `show_export_picklist()` method and a one-line edit to `show_main_menu()` in `menu.py`; and a new `_handle_export_resources()` handler plus dispatch wiring in `main.py`.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `json`, `pathlib`, `shutil`, `datetime`, `tempfile`). No third-party packages. Azure CLI (`az`) called via `subprocess.run`.

**Spec:** `docs/superpowers/specs/2026-04-09-export-resources-as-bicep-design.md`

---

## File Map

| Action | Path | Purpose |
| --- | --- | --- |
| Modify | `deployScript/azure_client.py` | Add `AzureResource` dataclass + 2 new methods (lines 14–26 for dataclass; append methods after line 456) |
| Create | `deployScript/exporter.py` | `ResourceExporter` class — all export orchestration |
| Modify | `deployScript/menu.py` | Add `[E]` to `show_main_menu()` options (line ~341); add `show_export_picklist()` method |
| Modify | `deployScript/main.py` | Instantiate `ResourceExporter` in `__init__` (after line 32); add `elif choice == "E"` (before line 108); add `_handle_export_resources()` method |
| Create | `tests/test_exporter.py` | Unit tests for pure functions (sanitize, wrap, file naming) |

---

## Task 1: AzureResource dataclass and CLI wrapper methods in azure_client.py

**Files:**
- Modify: `deployScript/azure_client.py` (lines 14–26 for dataclass placement; append after line 456)

### Background

`azure_client.py` already defines `AzureSubscription` at lines 14–26 as a `@dataclass`. The new `AzureResource` dataclass goes in the same block. Two new methods go at the end of the `AzureClient` class (after line 456).

`az resource list --resource-group <rg> --output json` returns a JSON array. Each element has keys: `id`, `name`, `type`, `location`.

`az resource show --ids <id> --output json` returns a single resource object (full ARM representation).

---

- [ ] **Step 1: Add `AzureResource` dataclass**

In `deployScript/azure_client.py`, after the existing `AzureSubscription` dataclass (around line 26), add:

```python
@dataclass
class AzureResourceGroup:
    # (already exists — do not duplicate)
    pass
```

Find the block that ends with `AzureResourceGroup` and add `AzureResource` immediately after it:

```python
@dataclass
class AzureResource:
    resource_id: str    # full ARM resource ID (/subscriptions/.../resourceGroups/...)
    name: str
    resource_type: str  # e.g. "Microsoft.Storage/storageAccounts"
    location: str
```

- [ ] **Step 2: Add `list_resource_group_resources` method to `AzureClient`**

Append at the end of `AzureClient` class in `deployScript/azure_client.py`:

```python
def list_resource_group_resources(self, resource_group: str) -> List['AzureResource']:
    """List all resources in a resource group."""
    try:
        az_cmd = self._get_az_command()
        result = subprocess.run(
            [az_cmd, 'resource', 'list', '--resource-group', resource_group, '--output', 'json'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logger.log(f"Error listing resources: {result.stderr}", LogLevel.ERROR, Color.RED)
            return []
        items = json.loads(result.stdout)
        return [
            AzureResource(
                resource_id=item['id'],
                name=item['name'],
                resource_type=item['type'],
                location=item.get('location', 'unknown')
            )
            for item in items
        ]
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
        logger.log(f"Error listing resources: {e}", LogLevel.ERROR, Color.RED)
        return []
```

- [ ] **Step 3: Add `get_resource_arm_json` method to `AzureClient`**

Append directly after `list_resource_group_resources`:

```python
def get_resource_arm_json(self, resource_id: str) -> Optional[dict]:
    """Get the full ARM JSON for a specific resource by its resource ID."""
    try:
        az_cmd = self._get_az_command()
        result = subprocess.run(
            [az_cmd, 'resource', 'show', '--ids', resource_id, '--output', 'json'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logger.log(f"Error fetching resource: {result.stderr}", LogLevel.ERROR, Color.RED)
            return None
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        logger.log(f"Error fetching resource ARM JSON: {e}", LogLevel.ERROR, Color.RED)
        return None
```

- [ ] **Step 4: Verify `AzureResource` is exported from `azure_client.py`**

Check that `azure_client.py` imports are sufficient — `List`, `Optional`, `dataclass` are already imported (they are used by `AzureSubscription` and `AzureResourceGroup`). No new imports needed.

- [ ] **Step 5: Commit**

```bash
git add deployScript/azure_client.py
git commit -m "feat: add AzureResource dataclass and resource listing methods to AzureClient"
```

---

## Task 2: ResourceExporter class (exporter.py)

**Files:**
- Create: `deployScript/exporter.py`
- Create: `tests/test_exporter.py`

### Background

`az bicep decompile --file foo.json` writes output to `foo.bicep` in the **same directory** as the input file — there is no `--outfile` flag. After decompile succeeds, the `.bicep` file must be **moved** to the intended destination using `shutil.move`.

The raw output of `az resource show` contains Azure-internal fields (`managedBy`, `etag`, `systemData`, etc.) that cause decompile warnings or failures. These must be stripped before wrapping in the ARM template envelope.

`az bicep decompile` may exit 0 but emit `"WARNING"` or `"Could not"` in stderr — this indicates incomplete output and must be treated as a failure.

File naming: take the last segment of `resource_type` after `/`, lowercase it, append `-{name}`. E.g. `Microsoft.Storage/storageAccounts` + `myaccount` → `storageaccounts-myaccount`.

---

- [ ] **Step 1: Write tests for pure functions first**

Create `tests/test_exporter.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from deployScript.exporter import ResourceExporter


class MockAzureClient:
    def get_resource_arm_json(self, resource_id):
        return None


class MockConfigManager:
    pass


def make_exporter():
    return ResourceExporter(MockAzureClient(), MockConfigManager())


# --- _make_output_filename ---

def test_filename_storage_account():
    e = make_exporter()
    assert e._make_output_filename("Microsoft.Storage/storageAccounts", "myaccount") == "storageaccounts-myaccount"

def test_filename_keyvault():
    e = make_exporter()
    assert e._make_output_filename("Microsoft.KeyVault/vaults", "mykeyvault") == "vaults-mykeyvault"

def test_filename_preserves_resource_name_case():
    e = make_exporter()
    # type slug is lowercased, name is kept as-is
    assert e._make_output_filename("Microsoft.Compute/virtualMachines", "MyVM") == "virtualmachines-MyVM"


# --- _sanitize_resource_for_arm ---

def test_sanitize_removes_internal_fields():
    e = make_exporter()
    raw = {
        "id": "/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sa",
        "name": "sa",
        "type": "Microsoft.Storage/storageAccounts",
        "apiVersion": "2021-09-01",
        "location": "eastus",
        "tags": {},
        "properties": {"primaryEndpoints": {}},
        "managedBy": None,
        "etag": "W/\"abc\"",
        "systemData": {"createdAt": "2021-01-01"},
        "identity": None,
        "changedTime": "2021-01-01",
        "createdTime": "2021-01-01",
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "managedBy" not in result
    assert "etag" not in result
    assert "systemData" not in result
    assert "identity" not in result
    assert "changedTime" not in result
    assert "createdTime" not in result
    assert result["name"] == "sa"
    assert result["apiVersion"] == "2021-09-01"

def test_sanitize_keeps_required_fields():
    e = make_exporter()
    raw = {
        "name": "sa",
        "type": "Microsoft.Storage/storageAccounts",
        "apiVersion": "2021-09-01",
        "location": "eastus",
        "tags": {"env": "prod"},
        "properties": {"foo": "bar"},
        "sku": {"name": "Standard_LRS"},
        "kind": "StorageV2",
    }
    result = e._sanitize_resource_for_arm(raw)
    assert result["sku"] == {"name": "Standard_LRS"}
    assert result["kind"] == "StorageV2"
    assert result["tags"] == {"env": "prod"}

def test_sanitize_non_null_identity_is_kept():
    e = make_exporter()
    raw = {
        "name": "sa",
        "type": "T",
        "apiVersion": "2021",
        "location": "eastus",
        "identity": {"type": "SystemAssigned", "principalId": "abc"},
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "identity" in result

def test_sanitize_null_identity_is_removed():
    e = make_exporter()
    raw = {
        "name": "sa",
        "type": "T",
        "apiVersion": "2021",
        "location": "eastus",
        "identity": None,
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "identity" not in result


# --- _wrap_arm_template ---

def test_wrap_produces_valid_arm_envelope():
    e = make_exporter()
    resource = {"name": "sa", "type": "Microsoft.Storage/storageAccounts", "apiVersion": "2021-09-01", "location": "eastus"}
    result = e._wrap_arm_template(resource)
    assert result["$schema"] == "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    assert result["contentVersion"] == "1.0.0.0"
    assert result["resources"] == [resource]
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd d:/repos/bicepDeployment
python -m pytest tests/test_exporter.py -v
```

Expected: All tests fail with `ModuleNotFoundError` or `AttributeError` — `exporter.py` does not exist yet.

- [ ] **Step 3: Create `deployScript/exporter.py`**

```python
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from .logger import logger, LogLevel, Color

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
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def export_resources(
        self,
        selected_resources: List['AzureResource'],
        output_dir: Path
    ) -> Tuple[int, int]:
        """
        Export each selected resource as a .bicep file into output_dir.
        Creates output_dir. Returns (success_count, total_count).
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            logger.log(f"Failed to create output directory {output_dir}: {e}", LogLevel.ERROR, Color.RED)
            return 0, len(selected_resources)

        success = 0
        total = len(selected_resources)

        for resource in selected_resources:
            stem = self._make_output_filename(resource.resource_type, resource.name)
            dest_bicep = output_dir / f"{stem}.bicep"

            # Fetch ARM JSON
            arm_json = self._fetch_arm_json(resource.resource_id)
            if arm_json is None:
                logger.log(f"❌ {resource.name}: failed to fetch ARM JSON", LogLevel.ERROR, Color.RED)
                continue

            # Sanitize and wrap
            sanitized = self._sanitize_resource_for_arm(arm_json)
            template = self._wrap_arm_template(sanitized)

            # Write to temp file in output_dir
            tmp_path = output_dir / f"_tmp_{stem}.json"
            try:
                tmp_path.write_text(json.dumps(template, indent=2), encoding='utf-8')
            except OSError as e:
                logger.log(f"❌ {resource.name}: failed to write temp file: {e}", LogLevel.ERROR, Color.RED)
                continue

            # Decompile
            ok, reason = self._decompile_to_bicep(tmp_path, dest_bicep)
            if ok:
                logger.log(f"✅ {stem}.bicep", LogLevel.SUCCESS, Color.GREEN)
                success += 1
            else:
                # _decompile_to_bicep deletes tmp_path — write fallback from in-memory template
                fallback = output_dir / f"{stem}.json"
                try:
                    fallback.write_text(json.dumps(template, indent=2), encoding='utf-8')
                except OSError:
                    pass
                logger.log(f"❌ {resource.name}: {reason}", LogLevel.ERROR, Color.RED)
                logger.log(f"   Raw ARM JSON saved as {stem}.json", LogLevel.WARN, Color.YELLOW)

        return success, total

    def _fetch_arm_json(self, resource_id: str) -> Optional[dict]:
        """Fetch full ARM JSON for a resource."""
        return self.azure_client.get_resource_arm_json(resource_id)

    def _sanitize_resource_for_arm(self, resource_json: dict) -> dict:
        """
        Strip Azure-internal fields that cause az bicep decompile to fail or warn.
        Keep: type, apiVersion, name, location, tags, properties, sku, kind, dependsOn.
        Remove: managedBy, etag, systemData, identity (if null), changedTime, createdTime, id.
        """
        always_remove = {'managedBy', 'etag', 'systemData', 'changedTime', 'createdTime', 'id'}
        result = {k: v for k, v in resource_json.items() if k not in always_remove}

        # Remove identity only if null
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
        Run az bicep decompile on tmp_json_path.
        Output lands at tmp_json_path.with_suffix('.bicep') — no --outfile flag exists.
        On success: move the produced .bicep to dest_bicep_path, delete tmp_json_path.
        On failure: delete tmp_json_path (and any partial .bicep), return (False, reason).
        """
        produced_bicep = tmp_json_path.with_suffix('.bicep')
        move_succeeded = False
        try:
            az_cmd = self.azure_client._get_az_command()
            result = subprocess.run(
                [az_cmd, 'bicep', 'decompile', '--file', str(tmp_json_path)],
                capture_output=True,
                text=True,
                check=False
            )

            failed = result.returncode != 0
            warned = not failed and ('WARNING' in result.stderr or 'Could not' in result.stderr)

            if failed or warned:
                reason = (result.stderr or result.stdout).strip()
                return False, reason or "decompile failed with no output"

            # Success: move produced .bicep to destination
            shutil.move(str(produced_bicep), str(dest_bicep_path))
            move_succeeded = True
            return True, ""

        except (subprocess.SubprocessError, OSError) as e:
            return False, str(e)
        finally:
            # Always delete the temp JSON input
            try:
                if tmp_json_path.exists():
                    tmp_json_path.unlink()
            except OSError:
                pass
            # Only delete the produced .bicep if we did NOT successfully move it
            # (after a successful move it no longer exists at produced_bicep, but guard
            # against the edge case where dest_bicep_path == produced_bicep)
            if not move_succeeded:
                try:
                    if produced_bicep.exists():
                        produced_bicep.unlink()
                except OSError:
                    pass

    def _make_output_filename(self, resource_type: str, name: str) -> str:
        """
        Derive output filename stem from resource type and name.
        'Microsoft.Storage/storageAccounts' + 'myaccount' -> 'storageaccounts-myaccount'
        """
        type_slug = resource_type.split('/')[-1].lower()
        return f"{type_slug}-{name}"
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd d:/repos/bicepDeployment
python -m pytest tests/test_exporter.py -v
```

Expected output:
```
tests/test_exporter.py::test_filename_storage_account PASSED
tests/test_exporter.py::test_filename_keyvault PASSED
tests/test_exporter.py::test_filename_preserves_resource_name_case PASSED
tests/test_exporter.py::test_sanitize_removes_internal_fields PASSED
tests/test_exporter.py::test_sanitize_keeps_required_fields PASSED
tests/test_exporter.py::test_sanitize_non_null_identity_is_kept PASSED
tests/test_exporter.py::test_sanitize_null_identity_is_removed PASSED
tests/test_exporter.py::test_wrap_produces_valid_arm_envelope PASSED
8 passed
```

If any fail, fix `exporter.py` until all 8 pass before continuing.

- [ ] **Step 5: Commit**

```bash
git add deployScript/exporter.py tests/test_exporter.py
git commit -m "feat: add ResourceExporter class with sanitize, wrap, decompile, and file naming"
```

---

## Task 3: show_export_picklist and show_main_menu edit in menu.py

**Files:**
- Modify: `deployScript/menu.py` (lines ~341 for options edit; append new method near end)

### Background

`show_main_menu()` builds an `options` list (lines 325–351) and ends with `"[Q] Quit"`. Insert `"[E] Export from Azure"` immediately before `"[Q] Quit"`.

`show_reorder_menu()` (lines 367–486) is the pattern to follow for arrow-key navigation. Key mapping: `_get_key()` returns strings like `'UP'`, `'DOWN'`, `'ENTER'`, `'ESC'`, or the raw character (`'Q'`, `'A'`, `' '` for space).

The picklist renders each resource as one row with a checkbox, name, type, and location. `Space` toggles selection; `A` selects all; `N` clears all; `Enter` confirms returning the selected list; `Q` returns `None`.

`AzureResource` must be imported at the top of `menu.py`.

---

- [ ] **Step 1: Add `AzureResource` import to `menu.py`**

In `deployScript/menu.py`, find the existing import line:

```python
from .azure_client import AzureClient, AzureSubscription, AzureResourceGroup
```

Change it to:

```python
from .azure_client import AzureClient, AzureSubscription, AzureResourceGroup, AzureResource
```

- [ ] **Step 2: Add `[E] Export from Azure` to `show_main_menu()` options list**

In `deployScript/menu.py`, in `show_main_menu()`, find the options block that ends with `"[Q] Quit"`:

```python
        options.extend([
            "[O] Reorder",
            "[P] Parameters", 
            "[R] Refresh",
            "[C] Config",
            "[Q] Quit"
        ])
```

Change it to:

```python
        options.extend([
            "[O] Reorder",
            "[P] Parameters",
            "[R] Refresh",
            "[C] Config",
            "[E] Export from Azure",
            "[Q] Quit"
        ])
```

- [ ] **Step 3: Add `show_export_picklist` method to `MenuSystem`**

Append the following method to the `MenuSystem` class in `deployScript/menu.py` (before the last line of the class, after `_handle_chrome_profile_selection` or any other last method):

```python
def show_export_picklist(self, resources: List[AzureResource]) -> Optional[List[AzureResource]]:
    """
    Show a multi-select picklist of Azure resources.
    Returns selected list on Enter (may be empty), None on Q (cancel).
    Controls: ↑↓ navigate, Space toggle, A=all, N=none, Enter=confirm, Q=cancel.
    """
    selected = set()  # indices of selected resources
    current = 0       # currently highlighted index

    while True:
        self.clear_screen()
        console_width = self._get_console_width()
        separator = "=" * console_width

        header = "EXPORT FROM AZURE — SELECT RESOURCES"
        padding = (console_width - len(header)) // 2
        print(separator)
        print(" " * padding + header)
        print(separator)
        print()
        print(f"  {Color.GRAY}↑↓ navigate  |  Space toggle  |  [A] all  |  [N] none  |  Enter confirm  |  [Q] cancel{Color.RESET}")
        print()

        for i, resource in enumerate(resources):
            check = f"{Color.GREEN}✓{Color.RESET}" if i in selected else " "
            type_slug = resource.resource_type.split("/")[-1]
            row = f"[{check}] {resource.name}  {Color.GRAY}|  {type_slug}  |  {resource.location}{Color.RESET}"
            if i == current:
                print(f"  {Color.CYAN}→{Color.RESET} {row}")
            else:
                print(f"    {row}")

        print()
        count = len(selected)
        print(f"  {Color.CYAN}{count} selected{Color.RESET}")
        print(separator)

        key = self._get_key()

        if key == 'UP':
            current = max(0, current - 1)
        elif key == 'DOWN':
            current = min(len(resources) - 1, current + 1)
        elif key == ' ':
            if current in selected:
                selected.discard(current)
            else:
                selected.add(current)
        elif key == 'A':
            selected = set(range(len(resources)))
        elif key == 'N':
            selected = set()
        elif key == 'ENTER':
            return [resources[i] for i in sorted(selected)]
        elif key in ('Q', 'ESC'):
            return None
```

- [ ] **Step 4: Smoke-test the import chain**

```bash
cd d:/repos/bicepDeployment
python -c "from deployScript.menu import MenuSystem; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 5: Re-run existing tests to confirm no regression**

```bash
python -m pytest tests/ -v
```

Expected: all 8 existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add deployScript/menu.py
git commit -m "feat: add [E] Export to main menu and show_export_picklist to MenuSystem"
```

---

## Task 4: _handle_export_resources and dispatch wiring in main.py

**Files:**
- Modify: `deployScript/main.py`

### Background

`main.py`'s `__init__` (lines 16–32) instantiates all managers. `ResourceExporter` goes there.

The key dispatch chain is at lines 82–116. The new `elif choice == "E":` must be added **before** the `elif choice.isdigit():` branch (line 108) — alongside the other letter-key branches.

`_handle_export_resources` must import `datetime` (already available? check — `from datetime import datetime` may be needed). `Path` is already imported via `pathlib`.

---

- [ ] **Step 1: Add `ResourceExporter` import and instantiation**

In `deployScript/main.py`, find the existing imports at the top of the file and add:

```python
from .exporter import ResourceExporter
```

Then in `__init__`, after `self.menu_system = MenuSystem(...)`, add:

```python
self.exporter = ResourceExporter(self.azure_client, self.config_manager)
```

- [ ] **Step 2: Ensure `datetime` is imported in `main.py`**

At the top of `deployScript/main.py`, check for `from datetime import datetime`. If absent, add it alongside the other stdlib imports.

- [ ] **Step 3: Add `elif choice == "E":` to dispatch chain**

In the main loop dispatch (around line 105), find the block ending in `isdigit()`:

```python
                elif choice == "C":
                    self.menu_system.show_configuration_menu()
                    
                elif choice.isdigit():
                    self._handle_deploy_individual(templates, int(choice))
```

Insert the new branch **between `"C"` and `choice.isdigit()`** — it must come before any numeric/range checks so that `"E"` is caught as a letter-key branch:

```python
                elif choice == "C":
                    self.menu_system.show_configuration_menu()

                elif choice == "E":          # ← new — before isdigit check
                    self._handle_export_resources()

                elif choice.isdigit():       # ← unchanged, must remain after "E"
                    self._handle_deploy_individual(templates, int(choice))
```

(`"E".isdigit()` is `False`, so ordering does not affect correctness today, but placing it with the other letter-key branches (`A`, `V`, `O`, `P`, `R`, `C`) keeps the dispatch semantically consistent.)

- [ ] **Step 4: Add `_handle_export_resources` method**

Add the following method to the `BicepDeploymentScript` class in `deployScript/main.py`:

```python
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

    # Export
    success, total = self.exporter.export_resources(selected, output_dir)

    # Summary
    print()
    if success == total:
        logger.log(
            f"Exported {success}/{total} resources to {output_dir}/",
            LogLevel.SUCCESS, Color.GREEN
        )
    else:
        logger.log(
            f"Exported {success}/{total} resources to {output_dir}/ ({total - success} failed — see above)",
            LogLevel.WARN, Color.YELLOW
        )
    input("Press Enter to continue...")
```

- [ ] **Step 5: Smoke-test the full import chain**

```bash
cd d:/repos/bicepDeployment
python -c "from deployScript.main import BicepDeploymentScript; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all 8 tests pass.

- [ ] **Step 7: Manual smoke test — verify `[E]` appears in main menu**

```bash
python deploy.py
```

Expected: Main menu now shows `[E] Export from Azure` as one of the options. Press `Q` to exit without doing anything.

- [ ] **Step 8: Commit**

```bash
git add deployScript/main.py
git commit -m "feat: wire [E] Export from Azure handler into main menu dispatch"
```

---

## Task 5: End-to-end verification

**Files:** None modified — verification only.

### Background

This task verifies the full feature works against a real Azure environment. It requires being logged in with `az login` and having a resource group with at least one resource.

---

- [ ] **Step 1: Run the app and navigate to export**

```bash
python deploy.py
```

Press `[C]` → `[L]` to log in if not already logged in. Press `[C]` → `[R]` to set a Resource Group. Return to main menu.

- [ ] **Step 2: Test pre-flight blocks work**

Without being logged in: press `[E]` — should show login warning.
Without a resource group set: press `[E]` — should show RG warning.

- [ ] **Step 3: Test full export flow**

With a logged-in session and a resource group set: press `[E]`. Verify:
- Resource list loads and displays
- Arrow keys navigate, Space selects, A/N work
- Enter starts export
- Progress lines print per resource (`✅` or `❌`)
- Summary line shows correct count
- `exported/YYYY-MM-DD_HHMMSS/` folder is created with `.bicep` files (or `.json` fallbacks)

- [ ] **Step 4: Verify existing `.bicep` files in root are untouched**

```bash
ls *.bicep
```

Files in the root directory must be unchanged.

- [ ] **Step 5: Final commit if any small fixes were needed**

```bash
git add -p
git commit -m "fix: export smoke test corrections"
```

---

## Summary

| Task | Deliverable |
| --- | --- |
| 1 | `AzureResource` dataclass + `list_resource_group_resources` + `get_resource_arm_json` in `azure_client.py` |
| 2 | `deployScript/exporter.py` with `ResourceExporter` + `tests/test_exporter.py` with 8 passing tests |
| 3 | `show_export_picklist()` in `menu.py` + `[E]` added to `show_main_menu()` options |
| 4 | `_handle_export_resources()` + dispatch wiring in `main.py` |
| 5 | End-to-end manual verification against live Azure |
