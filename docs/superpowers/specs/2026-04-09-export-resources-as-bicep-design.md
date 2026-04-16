# Design: Export Azure Resource Group Resources as Bicep Files

**Date:** 2026-04-09
**Status:** Approved

---

## Overview

Add a dedicated export screen (accessible from the main menu via `[E] Export from Azure`) that lists all resources in the configured Resource Group, lets the user select individual resources from a picklist, then exports each selected resource as an individual `.bicep` file into a timestamped subfolder (`exported/YYYY-MM-DD_HHMMSS/`) relative to the working directory (same root as the `.bicep` files). This avoids overwriting any existing working `.bicep` files in the root directory.

---

## Architecture

### New file: `deployScript/exporter.py`

Contains all export logic as a single `ResourceExporter` class. Receives `AzureClient` and `ConfigManager` via constructor injection — same pattern as `MenuSystem` and `DeploymentManager`:

```python
class ResourceExporter:
    def __init__(self, azure_client: AzureClient, config_manager: ConfigManager):
        self.azure_client = azure_client
        self.config_manager = config_manager
```

**Methods:**

- `check_bicep_available() -> bool`
  Runs `az bicep version` and returns `True` if exit code is 0. Called by `_handle_export_resources()` before entering the export screen — not per-resource.

- `export_resources(selected_resources: List[AzureResource], output_dir: Path) -> Tuple[int, int]`
  Creates `output_dir` itself (`output_dir.mkdir(parents=True, exist_ok=False)`). Orchestrates the per-resource loop. Returns `(success_count, total_count)`.

- `_fetch_arm_json(resource_id: str) -> Optional[dict]`
  Calls `self.azure_client.get_resource_arm_json(resource_id)`.

- `_sanitize_resource_for_arm(resource_json: dict) -> dict`
  Strips Azure-internal fields that cause `az bicep decompile` to fail or warn: `managedBy`, `etag`, `systemData`, `identity` (when null), `changedTime`, `createdTime`. Keeps: `type`, `apiVersion`, `name`, `location`, `tags`, `properties`, `sku`, `kind`. The `apiVersion` field is required for decompile — if absent in the raw JSON, it must be added; `az resource show` returns it at the top-level `apiVersion` key.

- `_wrap_arm_template(sanitized_resource: dict) -> dict`
  Wraps a sanitized resource dict in the ARM deployment template envelope:

  ```json
  {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "resources": [ "<sanitized_resource>" ]
  }
  ```

- `_decompile_to_bicep(tmp_json_path: Path, dest_bicep_path: Path) -> Tuple[bool, str]`
  Runs `az bicep decompile --file <tmp_json_path>`. The tool writes output to `<tmp_json_path stem>.bicep` in the same directory (no `--outfile` flag exists). After the call:
  - If exit code is non-zero: return `(False, stderr)`
  - If exit code is 0 but stderr contains `"WARNING"` or `"Could not"`: return `(False, stderr)` — decompile warnings indicate incomplete output, treat as failure
  - Otherwise: move `<tmp_json_path>.bicep` → `dest_bicep_path`, return `(True, "")`

  Temp `.json` file and any produced `.bicep` file adjacent to it are always deleted after the call regardless of outcome. On failure the raw ARM JSON is preserved as the fallback at `dest_bicep_path.with_suffix(".json")`.

---

### Changes to `azure_client.py`

**New dataclass** (add near top of file alongside `AzureSubscription`):

```python
@dataclass
class AzureResource:
    resource_id: str    # full ARM resource ID
    name: str
    resource_type: str  # e.g. "Microsoft.Storage/storageAccounts"
    location: str
```

**New methods:**

- `list_resource_group_resources(resource_group: str) -> List[AzureResource]`
  Calls `az resource list --resource-group <rg> --output json`. Maps response using keys `id` → `resource_id`, `name`, `type` → `resource_type`, `location`. Returns empty list on failure.

- `get_resource_arm_json(resource_id: str) -> Optional[dict]`
  Calls `az resource show --ids <id> --output json`. Returns parsed dict or `None` on non-zero exit.

---

### Changes to `menu.py`

**Edit `show_main_menu()`:** Add `"[E] Export from Azure"` to the `options` list, before `"[Q] Quit"`.

**New method:** `show_export_picklist(resources: List[AzureResource]) -> Optional[List[AzureResource]]`

- Arrow key navigation (same `_get_key()` pattern as `show_reorder_menu`)
- `Space` toggles selection on highlighted resource
- `[A]` selects all, `[N]` clears all
- `Enter` confirms — returns the list of selected `AzureResource` objects (empty list `[]` if none selected)
- `Q` cancels — returns `None` to signal cancellation (distinct from confirming with nothing selected)
- Each row: `[✓] storageaccounts-myaccount  |  Microsoft.Storage/storageAccounts  |  eastus`

---

### Changes to `main.py`

- Instantiate `ResourceExporter` in `__init__` alongside other managers: `self.exporter = ResourceExporter(self.azure_client, self.config_manager)`
- Add `elif choice == "E":` in the key-dispatch chain, alongside the other letter-key branches (before the `isdigit` check)
- New method `_handle_export_resources()`:
  1. Check login: `self.azure_client.test_azure_login()` — if not logged in, show message and return
  2. Check resource group: `self.config_manager.get_resource_group()` — if not set, show message and return
  3. Check bicep: `self.exporter.check_bicep_available()` — if not available, show message and return
  4. Print loading message, call `self.azure_client.list_resource_group_resources(rg)`
  5. If empty list, show message and return
  6. Call `self.menu_system.show_export_picklist(resources)`
  7. If result is `None` (Q pressed), return silently
  8. If result is `[]` (Enter with nothing selected), show "Nothing selected" and return
  9. Build `output_dir = Path("exported") / datetime.now().strftime("%Y-%m-%d_%H%M%S")` — relative to cwd, same root as `.bicep` files
  10. Call `success, total = self.exporter.export_resources(selected, output_dir)`
  11. Print `"Exported {success}/{total} resources to {output_dir}"` and wait for keypress

---

## Export Flow

```text
[E] pressed
    │
    ├─ Not logged in?           → "Not logged in. Use [C] Config → [L] Login first" → return
    ├─ No resource group set?   → "Set a Resource Group in [C] Config first" → return
    ├─ az bicep not available?  → "az bicep not found — run: az bicep install" → return
    │
    ├─ "Loading resources..." → az resource list
    ├─ Empty?  → "No resources found in <rg>" → return
    │
    ├─ show_export_picklist() →
    │       Q pressed            → return silently
    │       Enter, nothing selected → "Nothing selected" → return
    │
    ├─ Build output_dir: Path("exported") / "YYYY-MM-DD_HHMMSS"  (relative to cwd)
    ├─ exporter.export_resources() creates output_dir
    │
    └─ For each selected resource:
           self.azure_client.get_resource_arm_json(id)  → None → log ❌, continue
           _sanitize_resource_for_arm()
           _wrap_arm_template()
           Write ARM JSON to tmp file inside output_dir
           az bicep decompile --file <tmp>
           Success → move <tmp>.bicep → <type-name>.bicep, delete tmp
           Failure → log ❌ + reason, save raw ARM JSON as <type-name>.json, delete tmp
    │
    └─ "Exported X/Y resources to exported/YYYY-MM-DD_HHMMSS/"
       Press any key to return
```

---

## Output File Naming

Pattern: `{type-slug}-{name}.bicep`

- Take the segment after the last `/` in `resource_type`, lowercase it, append `-{name}`
- Examples:
  - `Microsoft.Storage/storageAccounts`, name `myaccount` → `storageaccounts-myaccount.bicep`
  - `Microsoft.KeyVault/vaults`, name `mykeyvault` → `vaults-mykeyvault.bicep`
- Fallback JSON uses same stem: `storageaccounts-myaccount.json`

---

## Error Handling

| Scenario | Behaviour |
| --- | --- |
| Not logged in | Block entry: "Not logged in. Use [C] Config → [L] Login first" |
| No resource group configured | Block entry: "Set a Resource Group in [C] Config first" |
| `az bicep` not installed | Block entry: "az bicep not found — run: az bicep install" |
| `az resource list` returns empty | "No resources found in resource group `<rg>`" → return |
| `az resource show` fails for a resource | Log `❌ <name>: <stderr>`, continue to next |
| `az bicep decompile` exits non-zero | Log `❌ <name>: decompile failed — <reason>`, keep raw `.json` |
| `az bicep decompile` exits 0 with warnings | Treated as failure — log warning text, keep raw `.json` |
| Output folder creation fails | Abort with error message, exit export screen |
| Q on picklist | Return to main menu silently |
| Enter on picklist with nothing selected | "Nothing selected" message, return to main menu |
| Single resource failure | Log and continue — partial export preferred over full abort |

---

## Folder Structure After Export

```text
(working directory)/
├── storage.bicep               ← existing working files untouched
├── keyvault.bicep
├── exported/
│   └── 2026-04-09_143200/
│       ├── storageaccounts-myaccount.bicep
│       ├── vaults-mykeyvault.bicep
│       └── virtualmachines-myvm.json   ← fallback if decompile failed
```

---

## Out of Scope

- Importing exported files back into the main deployment list (separate feature)
- Resolving cross-resource dependencies in exported Bicep
- Subscription scope export
- Filtering by resource type before the picklist
