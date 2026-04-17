# Workflow Mapping & Parameters Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store Azure resource name → workflowNames key → filename mappings in `.workflow-mappings.json`, use them during export and deployment, and generate bicep file headers dynamically from `parameters.local.json`.

**Architecture:** A new `workflow_mappings.py` module handles all mapping persistence. A new `header_generator.py` module replaces hardcoded header constants in `exporter.py` by reading `parameters.local.json`. A pre-pass in `_handle_export_resources()` in `main.py` resolves all mappings interactively before the export spinner starts. A pre-flight check in `main.py` warns when Incremental deployments would create a naming conflict with an existing Azure resource.

**Tech Stack:** Python 3.x, pytest, `json`, `re`, `pathlib`. No new dependencies.

---

## File Map

| Action | File | Responsibility |
| ------ | ---- | -------------- |
| Create | `deployScript/workflow_mappings.py` | `MappingEntry` dataclass + `WorkflowMappings` load/save/find/add |
| Create | `deployScript/header_generator.py` | Dynamic Bicep header generation from `parameters.local.json` |
| Create | `tests/test_workflow_mappings.py` | Unit tests for mapping module |
| Create | `tests/test_header_generator.py` | Unit tests for header generator |
| Modify | `deployScript/menu.py` | Add `show_workflow_mapping_picklist()` |
| Modify | `deployScript/exporter.py` | Use `WorkflowMappings` for filename, use `header_generator` instead of hardcoded headers |
| Modify | `deployScript/main.py` | Pre-pass mapping resolution, `parameters.local.json` update, pre-flight name check |

---

## Task 1: WorkflowMappings module

**Files:**
- Create: `deployScript/workflow_mappings.py`
- Create: `tests/test_workflow_mappings.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_workflow_mappings.py
import json
import pytest
from pathlib import Path
from deployScript.workflow_mappings import WorkflowMappings, MappingEntry


def test_load_returns_empty_when_file_missing(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_azure_name("anything") is None


def test_load_reads_existing_file(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    p.write_text(json.dumps({
        "test-bc": {"workflowKey": "bcDataHandler", "filename": "01.0-BC"}
    }))
    wm = WorkflowMappings(p).load()
    entry = wm.find_by_azure_name("test-bc")
    assert entry == MappingEntry(azure_name="test-bc", workflow_key="bcDataHandler", filename="01.0-BC")


def test_find_by_azure_name_missing_returns_none(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_azure_name("not-here") is None


def test_find_by_filename(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    p.write_text(json.dumps({
        "test-bc": {"workflowKey": "bcDataHandler", "filename": "01.0-BC"}
    }))
    wm = WorkflowMappings(p).load()
    entry = wm.find_by_filename("01.0-BC")
    assert entry.azure_name == "test-bc"
    assert entry.workflow_key == "bcDataHandler"


def test_find_by_filename_missing_returns_none(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_filename("nope") is None


def test_add_and_save_round_trip(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    wm = WorkflowMappings(p).load()
    wm.add("GetCustomers", "bcCustomers", "11.1-GetCustomers")
    wm.save()

    wm2 = WorkflowMappings(p).load()
    entry = wm2.find_by_azure_name("GetCustomers")
    assert entry.workflow_key == "bcCustomers"
    assert entry.filename == "11.1-GetCustomers"


def test_add_overwrites_existing_entry(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    wm = WorkflowMappings(p).load()
    wm.add("test-bc", "oldKey", "old-file")
    wm.add("test-bc", "newKey", "new-file")
    entry = wm.find_by_azure_name("test-bc")
    assert entry.workflow_key == "newKey"
    assert entry.filename == "new-file"


def test_add_returns_mapping_entry(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    entry = wm.add("test-bc", "bcDataHandler", "01.0-BC")
    assert isinstance(entry, MappingEntry)
    assert entry.azure_name == "test-bc"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd d:/repos/bicepDeployment
python -m pytest tests/test_workflow_mappings.py -v
```
Expected: ImportError (module does not exist yet)

- [ ] **Step 3: Implement `deployScript/workflow_mappings.py`**

```python
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAPPINGS_FILENAME = ".workflow-mappings.json"


@dataclass
class MappingEntry:
    azure_name: str
    workflow_key: str
    filename: str


class WorkflowMappings:
    def __init__(self, path: Path = None):
        self._path = path or Path(MAPPINGS_FILENAME)
        self._data: dict = {}

    def load(self) -> 'WorkflowMappings':
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        return self

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')

    def find_by_azure_name(self, azure_name: str) -> Optional[MappingEntry]:
        entry = self._data.get(azure_name)
        if entry:
            return MappingEntry(
                azure_name=azure_name,
                workflow_key=entry['workflowKey'],
                filename=entry['filename'],
            )
        return None

    def find_by_filename(self, stem: str) -> Optional[MappingEntry]:
        for azure_name, entry in self._data.items():
            if entry['filename'] == stem:
                return MappingEntry(
                    azure_name=azure_name,
                    workflow_key=entry['workflowKey'],
                    filename=entry['filename'],
                )
        return None

    def add(self, azure_name: str, workflow_key: str, filename: str) -> MappingEntry:
        self._data[azure_name] = {'workflowKey': workflow_key, 'filename': filename}
        return MappingEntry(azure_name=azure_name, workflow_key=workflow_key, filename=filename)
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_workflow_mappings.py -v
```
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add deployScript/workflow_mappings.py tests/test_workflow_mappings.py
git commit -m "feat: add WorkflowMappings module with load/save/find/add"
```

---

## Task 2: Dynamic header generator

**Files:**
- Create: `deployScript/header_generator.py`
- Create: `tests/test_header_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_header_generator.py
import json
import pytest
from pathlib import Path
from deployScript.header_generator import (
    generate_logic_app_header,
    generate_keyvault_header,
    _infer_bicep_type,
    _is_used_in_body,
)


def _write_params(tmp_path, params_dict):
    """Write a parameters.local.json with the given key→value dict."""
    data = {
        "$schema": "...",
        "contentVersion": "1.0.0.0",
        "parameters": {k: {"value": v} for k, v in params_dict.items()},
    }
    p = tmp_path / "parameters.local.json"
    p.write_text(json.dumps(data))
    return p


def test_infer_type_string():
    assert _infer_bicep_type("hello") == "string"


def test_infer_type_int():
    assert _infer_bicep_type(42) == "int"


def test_infer_type_bool():
    assert _infer_bicep_type(True) == "bool"


def test_infer_type_object():
    assert _infer_bicep_type({}) == "object"
    assert _infer_bicep_type({"a": 1}) == "object"


def test_infer_type_array():
    assert _infer_bicep_type([]) == "array"


def test_is_used_detects_word_boundary():
    body = "  state: logicAppState\n  location: resourceGroup().location"
    assert _is_used_in_body("logicAppState", body) is True
    assert _is_used_in_body("state", body) is True  # substring match too (Bicep uses word-level properties)
    assert _is_used_in_body("notPresent", body) is False


def test_logic_app_header_required_params_declared_without_suppress(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {"bcCustomers": "11.1"},
        "logicAppState": "Disabled",
        "storageAccount": {},
    }
    p = _write_params(tmp_path, params)
    body = "  state: logicAppState"
    header = generate_logic_app_header(body, p, "bcCustomers")
    assert "param environment string\n" in header
    assert "param projectSuffix string\n" in header
    assert "param workflowNames object\n" in header
    assert "param logicAppState string\n" in header


def test_logic_app_header_unused_params_get_suppress(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
        "storageAccount": {},
        "secretValues": {"key": "val"},
    }
    p = _write_params(tmp_path, params)
    body = "  state: logicAppState"  # storageAccount and secretValues not referenced
    header = generate_logic_app_header(body, p, "someKey")
    assert "#disable-next-line no-unused-params\nparam storageAccount object" in header
    assert "@secure()\n#disable-next-line no-unused-params\nparam secretValues object" in header


def test_logic_app_header_var_block(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
    }
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, "bcDataHandler")
    assert "var prefix = 'la-${environment}-${projectSuffix}'" in header
    assert "var nameOfLogicApp = '${prefix}-${workflowNames.bcDataHandler}'" in header


def test_logic_app_header_unknown_key_emits_placeholder(tmp_path):
    params = {"environment": "dev", "projectSuffix": "la-", "workflowNames": {}, "logicAppState": "Disabled"}
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, None)
    assert "workflowNames.UNKNOWN" in header


def test_keyvault_header_has_kv_var_block(tmp_path):
    params = {"environment": "dev", "projectSuffix": "la-", "logicAppState": "Disabled"}
    p = _write_params(tmp_path, params)
    header = generate_keyvault_header("", p)
    assert "var prefix = 'kv-${environment}'" in header
    assert "var nameOfKeyVault = '${prefix}-${uniqueString(resourceGroup().id)}'" in header


def test_object_param_with_empty_default_gets_default(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
        "storageAccount": {},
    }
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, "key")
    assert "param storageAccount object = {}" in header
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_header_generator.py -v
```
Expected: ImportError (module does not exist yet)

- [ ] **Step 3: Implement `deployScript/header_generator.py`**

```python
import json
import re
from pathlib import Path
from typing import Optional


def _infer_bicep_type(value) -> str:
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        return 'array'
    return 'object'


def _is_used_in_body(param_name: str, body: str) -> bool:
    return bool(re.search(rf'\b{re.escape(param_name)}\b', body))


def _load_params(parameters_file: Path) -> dict:
    """Read parameters from parameters.local.json, unwrapping the Azure format."""
    data = json.loads(parameters_file.read_text(encoding='utf-8'))
    return {k: v['value'] for k, v in data['parameters'].items()}


def _emit_param_lines(key: str, value, used: bool) -> list:
    """Return the lines (as strings) to emit for one parameter declaration."""
    btype = _infer_bicep_type(value)
    default = ' = {}' if (btype == 'object' and value == {}) else ''
    lines = []
    if key == 'secretValues':
        lines.append('@secure()')
    if not used:
        lines.append('#disable-next-line no-unused-params')
    lines.append(f'param {key} {btype}{default}')
    return lines


def generate_logic_app_header(
    body: str,
    parameters_file: Path,
    workflow_key: Optional[str],
) -> str:
    """
    Generate the standard Logic App bicep header from parameters.local.json.

    Required params (environment, projectSuffix, workflowNames, logicAppState) are
    always declared without suppress regardless of body usage.
    All other params follow usage detection.
    """
    params = _load_params(parameters_file)
    required = {'environment', 'projectSuffix', 'workflowNames', 'logicAppState'}
    lines = []

    # Required params first, in fixed order
    for key in ['environment', 'projectSuffix', 'workflowNames', 'logicAppState']:
        if key not in params:
            continue
        lines.extend(_emit_param_lines(key, params[key], used=True))

    lines.append('')

    # Remaining params, usage-detected
    for key, value in params.items():
        if key in required:
            continue
        used = _is_used_in_body(key, body)
        lines.extend(_emit_param_lines(key, value, used=used))

    # Var block
    lines.append('')
    lines.append("var prefix = 'la-${environment}-${projectSuffix}'")
    wkey = workflow_key if workflow_key else 'UNKNOWN'
    lines.append(f"var nameOfLogicApp = '${{prefix}}-${{workflowNames.{wkey}}}'")
    lines.append('')

    return '\n'.join(lines)


def generate_keyvault_header(body: str, parameters_file: Path) -> str:
    """
    Generate the standard Key Vault bicep header from parameters.local.json.

    Only 'environment' is declared without suppress. All others follow usage detection.
    """
    params = _load_params(parameters_file)
    required = {'environment'}
    lines = []

    if 'environment' in params:
        lines.extend(_emit_param_lines('environment', params['environment'], used=True))

    lines.append('')

    for key, value in params.items():
        if key in required:
            continue
        used = _is_used_in_body(key, body)
        lines.extend(_emit_param_lines(key, value, used=used))

    lines.append('')
    lines.append("// Limitation of Key Vault name to 24 characters")
    lines.append("var prefix = 'kv-${environment}'")
    lines.append("var nameOfKeyVault = '${prefix}-${uniqueString(resourceGroup().id)}'")
    lines.append('')

    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_header_generator.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add deployScript/header_generator.py tests/test_header_generator.py
git commit -m "feat: add dynamic bicep header generator from parameters.local.json"
```

---

## Task 3: Mapping picklist UI

**Files:**
- Modify: `deployScript/menu.py` (add `show_workflow_mapping_picklist()`)

- [ ] **Step 1: Add `show_workflow_mapping_picklist()` to `MenuSystem` in `menu.py`**

Add this method after `show_export_picklist`. It uses the existing `_get_key()` and `clear_screen()` methods:

```python
def show_workflow_mapping_picklist(
    self,
    azure_name: str,
    workflow_names: dict,
) -> Optional[tuple]:
    """
    Show a single-select picklist for mapping an Azure resource name to a workflowNames key.

    workflow_names: dict of {key: value} from parameters.local.json workflowNames.value
    Returns (workflow_key, is_new) where is_new=True if the user typed a new key.
    Returns None if the user skipped with Q.
    """
    keys = list(workflow_names.keys())
    NEW_KEY_SENTINEL = '__new__'
    items = keys + [NEW_KEY_SENTINEL]
    current = 0

    while True:
        self.clear_screen()
        console_width = self._get_console_width()
        separator = '=' * console_width
        print(separator)
        print(f"  No mapping found for '{Color.CYAN}{azure_name}{Color.RESET}'")
        print(f"  Select the {Color.WHITE}workflowNames{Color.RESET} key this workflow maps to:")
        print(separator)
        print(f"  {Color.GRAY}UP/DOWN navigate   Enter select   Q skip{Color.RESET}\n")

        for i, item in enumerate(items):
            leader = f"{Color.CYAN}▶{Color.RESET}" if i == current else " "
            if item == NEW_KEY_SENTINEL:
                print(f"  {leader}  {Color.YELLOW}[ New key ]{Color.RESET}")
            else:
                value = workflow_names[item]
                print(f"  {leader}  {Color.WHITE}{item:<30}{Color.RESET}  {Color.GRAY}→ {value}{Color.RESET}")

        print(f"\n{separator}")

        key = self._get_key()

        if key == 'UP':
            current = max(0, current - 1)
        elif key == 'DOWN':
            current = min(len(items) - 1, current + 1)
        elif key == 'ENTER':
            selected = items[current]
            if selected == NEW_KEY_SENTINEL:
                print()
                new_key = input("  Enter new camelCase key name: ").strip()
                if new_key:
                    return (new_key, True)
                # empty input → go back to picklist
            else:
                return (selected, False)
        elif key in ('Q', 'ESC'):
            return None
```

- [ ] **Step 2: Verify the import chain is intact**

```
cd d:/repos/bicepDeployment
python -c "from deployScript.menu import MenuSystem; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add deployScript/menu.py
git commit -m "feat: add workflow mapping picklist to MenuSystem"
```

---

## Task 4: Wire exporter to use mappings and dynamic headers

**Files:**
- Modify: `deployScript/exporter.py`
- Modify: `tests/test_exporter.py`

The exporter receives `WorkflowMappings` and `parameters_file` via `export_resources()`. The `_apply_standard_header()` method is updated to use `header_generator` functions. The `_LA_HEADER_TEMPLATE`, `_KV_HEADER` module-level constants and `_apply_logic_app_header()`, `_apply_keyvault_header()`, `_to_camel_case()` methods are removed.

- [ ] **Step 1: Add tests for new exporter behavior**

Add these to `tests/test_exporter.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from deployScript.workflow_mappings import WorkflowMappings


def _make_params_file(tmp_path, extra=None):
    params = {
        "environment": {"value": "dev"},
        "projectSuffix": {"value": "la-"},
        "workflowNames": {"value": {}},
        "logicAppState": {"value": "Disabled"},
    }
    if extra:
        params.update(extra)
    p = tmp_path / "parameters.local.json"
    p.write_text(json.dumps({"$schema": "...", "contentVersion": "1.0.0.0", "parameters": params}))
    return p


def test_export_uses_mapped_filename(tmp_path):
    """When a mapping exists, the output file should use mapping.filename."""
    from deployScript.exporter import ResourceExporter

    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    wm.add("GetCustomers", "bcCustomers", "11.1-GetCustomers")
    params_file = _make_params_file(tmp_path)

    exporter = ResourceExporter(MagicMock(), MagicMock())
    # Patch internal calls so only filename logic is tested
    exporter._fetch_arm_template = MagicMock(return_value={"resources": []})
    exporter._decompile_to_bicep = MagicMock(return_value=(False, "skip"))

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # Simulate the stem resolution (unit-test the helper directly)
    resource = MagicMock()
    resource.resource_type = "Microsoft.Logic/workflows"
    resource.name = "GetCustomers"

    stem = exporter._resolve_export_stem(resource, wm)
    assert stem == "11.1-GetCustomers"


def test_export_uses_default_stem_when_no_mapping(tmp_path):
    from deployScript.exporter import ResourceExporter

    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    exporter = ResourceExporter(MagicMock(), MagicMock())

    resource = MagicMock()
    resource.resource_type = "Microsoft.Logic/workflows"
    resource.name = "GetCustomers"

    stem = exporter._resolve_export_stem(resource, wm)
    assert stem == "workflows-GetCustomers"
```

- [ ] **Step 2: Run new tests to verify they fail**

```
python -m pytest tests/test_exporter.py::test_export_uses_mapped_filename tests/test_exporter.py::test_export_uses_default_stem_when_no_mapping -v
```
Expected: AttributeError (`_resolve_export_stem` does not exist yet)

- [ ] **Step 3: Update `deployScript/exporter.py`**

Make the following changes:

**3a.** Remove the `_LA_HEADER_TEMPLATE` and `_KV_HEADER` module-level constants and the `_apply_logic_app_header`, `_apply_keyvault_header`, `_to_camel_case` methods.

**3b.** Add imports at the top:

```python
from .workflow_mappings import WorkflowMappings, MappingEntry
from .header_generator import generate_logic_app_header, generate_keyvault_header
```

**3c.** Update `export_resources` signature to accept optional mapping/params args:

```python
def export_resources(
    self,
    selected_resources: List['AzureResource'],
    output_dir: Path,
    workflow_mappings: Optional['WorkflowMappings'] = None,
    parameters_file: Optional[Path] = None,
) -> Tuple[int, int]:
```

**3d.** Inside the loop, replace the `stem` calculation with `_resolve_export_stem`:

```python
stem = self._resolve_export_stem(resource, workflow_mappings)
```

**3e.** Replace the `_apply_standard_header` call to pass the new args:

```python
self._apply_standard_header(dest_bicep, workflow_mappings, parameters_file)
```

**3f.** Add `_resolve_export_stem` method:

```python
def _resolve_export_stem(self, resource: 'AzureResource', workflow_mappings: Optional['WorkflowMappings']) -> str:
    """Return the output filename stem for a resource, using mapping if available."""
    if workflow_mappings and 'Microsoft.Logic/workflows' in resource.resource_type:
        entry = workflow_mappings.find_by_azure_name(resource.name)
        if entry:
            return entry.filename
    return self._make_output_filename(resource.resource_type, resource.name)
```

**3g.** Replace `_apply_standard_header` and sub-methods with a version that uses `header_generator`:

```python
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
```

- [ ] **Step 4: Run all exporter tests**

```
python -m pytest tests/test_exporter.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add deployScript/exporter.py tests/test_exporter.py
git commit -m "feat: wire exporter to use WorkflowMappings and dynamic header generator"
```

---

## Task 5: Pre-pass mapping resolution and pre-flight check in main.py

**Files:**
- Modify: `deployScript/main.py`

This task has two parts: (A) pre-pass mapping resolution before export, (B) pre-flight name conflict check before Incremental deployments.

- [ ] **Step 1: Add imports to `main.py`**

Add at the top alongside existing imports. `main.py` does not currently import `json`, `re`, or `Optional` — all three are required by the new helpers:

```python
import json
import re
from typing import Optional
from .workflow_mappings import WorkflowMappings
from .header_generator import _load_params  # for resolving expected name
```

- [ ] **Step 2: Add `_resolve_workflow_mapping_for_resource` helper to `DeployScript`**

```python
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

    # Resolve filename:
    # - For an existing key: scan bicep/ for a file already referencing workflowNames.<key>
    # - For a new key: the file doesn't exist in bicep/ yet, skip the scan
    if is_new:
        filename = f"workflows-{resource.name}"
    else:
        filename = self._find_bicep_filename_for_key(key) or f"workflows-{resource.name}"

    wm.add(resource.name, key, filename)
    wm.save()

    self._upsert_workflow_name_in_params(key, resource.name)
    workflow_names[key] = resource.name  # keep in-memory dict in sync
```

- [ ] **Step 3: Add `_find_bicep_filename_for_key` helper**

```python
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
```

- [ ] **Step 4: Add `_upsert_workflow_name_in_params` helper**

```python
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
```

- [ ] **Step 5: Update `_handle_export_resources` to run the pre-pass before the spinner**

Find the section just before the spinner call and replace:

```python
        # Export (with spinner)
        success, total = logger.show_progress_spinner(
            f"Exporting {len(selected)} resource(s)",
            self.exporter.export_resources,
            selected,
            output_dir
        )
```

With:

```python
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
```

- [ ] **Step 6: Add `_check_logic_app_name_conflict` pre-flight helper**

```python
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

    # Read expected name from parameters.local.json
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

    # Check if resources already exist in the RG
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
```

- [ ] **Step 7: Add `_deploy_with_override` helper for the "use-exported" case**

When the user picks [U], we write a temporary parameter file with the workflow name overridden, deploy with it, then delete it:

```python
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
```

- [ ] **Step 8: Wire pre-flight into `_handle_deploy_individual`**

In `_handle_deploy_individual`, find the existing `deploy_result = self.deployment_manager.deploy_bicep_template(...)` call (around line 574) and replace the entire block from that line through the closing `)` with:

```python
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
```

- [ ] **Step 9: Wire pre-flight into the per-template loop in `_handle_deploy_range`**

In `_handle_deploy_range`, add `wm = WorkflowMappings().load()` once before the `for i, (num, template) in enumerate(selected_templates, 1):` loop. Inside the loop, find the existing `deploy_result = self.deployment_manager.deploy_bicep_template(...)` call and replace it with:

```python
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
```

- [ ] **Step 10: Verify import chain**

```
python -c "from deployScript.main import DeployScript; print('OK')"
```
Expected: `OK`

- [ ] **Step 11: Commit**

```bash
git add deployScript/main.py
git commit -m "feat: pre-pass mapping resolution and pre-flight name conflict check"
```

---

## Task 6: End-to-end smoke test

**Files:**
- No new files — manual verification steps

- [ ] **Step 1: Run full test suite**

```
cd d:/repos/bicepDeployment
python -m pytest tests/ -v
```
Expected: all existing + new tests PASS

- [ ] **Step 2: Verify `.workflow-mappings.json` round-trip**

```python
# Run from d:/repos/bicepDeployment
python -c "
from deployScript.workflow_mappings import WorkflowMappings
import tempfile, pathlib

with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / '.workflow-mappings.json'
    wm = WorkflowMappings(p).load()
    wm.add('test-bc', 'bcDataHandler', '01.0-BC')
    wm.save()
    wm2 = WorkflowMappings(p).load()
    entry = wm2.find_by_filename('01.0-BC')
    assert entry.workflow_key == 'bcDataHandler', f'Got {entry}'
    print('WorkflowMappings round-trip: OK')
"
```

- [ ] **Step 3: Verify header generator with real `parameters.local.json`**

```python
# Run from d:/repos/NewBicep (where parameters.local.json lives)
python -c "
import sys
sys.path.insert(0, 'd:/repos/bicepDeployment')
from deployScript.header_generator import generate_logic_app_header
from pathlib import Path

params = Path('parameters.local.json')
body = '  state: logicAppState\n  location: resourceGroup().location'
header = generate_logic_app_header(body, params, 'bcCustomers')
print(header[:500])
print('Header generation: OK')
"
```
Expected: prints a valid Bicep header block with `param environment string`, `param logicAppState string`, and `var nameOfLogicApp = '...'`

- [ ] **Step 4: Final commit**

```bash
cd d:/repos/bicepDeployment
git add -A
git status  # verify nothing unexpected is staged
git commit -m "feat: complete workflow mapping and dynamic parameter header integration"
```
