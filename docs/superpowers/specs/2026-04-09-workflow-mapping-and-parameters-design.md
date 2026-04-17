# Workflow Mapping & Parameters Integration Design

**Date:** 2026-04-09
**Project:** bicepDeployment / NewBicep
**Status:** Draft

---

## Overview

When exporting Logic App workflows from Azure as Bicep files, the system needs to:

1. Remember the relationship between Azure resource names and the friendly `workflowNames` keys used in `parameters.local.json`
2. Use the stored mapping to write exported files with the correct friendly filename
3. At deployment time, detect when a resource exists under its old exported name and warn before creating a duplicate
4. Generate bicep file headers dynamically from the actual parameters in `parameters.local.json` rather than hardcoded templates

---

## Data Model

### `.workflow-mappings.json`

A new file in the project root (alongside `parameters.local.json`). Committed to source control so mappings are shared across team members and environments.

```json
{
  "test-bc": {
    "workflowKey": "bcDataHandler",
    "filename": "01.0.BusinessCentral-Connection"
  },
  "GetCustomers": {
    "workflowKey": "bcCustomers",
    "filename": "11.1-GetCustomers"
  }
}
```

**Key:** Azure resource name (the actual Logic App name in Azure). Resource-group-agnostic — the same workflow has the same name across dev/accepttest/prod.

**`workflowKey`:** The camelCase key in `workflowNames` in `parameters.local.json`.

**`filename`:** The stem used when writing the `.bicep` file to the export folder (without `.bicep` extension).

Filename is determined at mapping time by:

1. Scanning the `bicep/` folder for a file that already references `workflowNames.<key>` in its content — if found, use that file's stem
2. Otherwise, default to `workflows-{azure-resource-name}`

Only Logic App workflows (`Microsoft.Logic/workflows`) are mapped. Other resource types (Key Vaults etc.) are exported with the default `{type-slug}-{azure-name}` filename and no mapping.

---

## Export Flow

### When a Logic App is exported

1. Look up the Azure resource name in `.workflow-mappings.json`
2. **Mapping found** → write the exported file as `{mapping.filename}.bicep`, no prompt
3. **No mapping found** → pause and show the interactive mapping picklist (see below)

### Interactive Mapping Picklist

Shown when no mapping exists for an exported Logic App. Uses cursor-key navigation (same pattern as the existing export resource picklist in `menu.py`):

```text
No mapping found for 'test-bc'. Select a workflowNames key:

  ▶  bcDataHandler         → 11.0-BCData-Handler
     bcCustomers           → 11.1-Customers
     helperGetErrorMessage → <PLACEHOLDER>
     helperSendNotification → <PLACEHOLDER>
     ...
     [ New key ]

↑/↓ navigate   Enter select   Q skip
```

The `→ <PLACEHOLDER>` text is the literal string `<PLACEHOLDER>` from the parameter value — shown as-is to help the user identify which keys are not yet configured.

- Arrow keys move the highlighted row
- `[New key]` is a navigable entry at the bottom of the list
- **Existing key selected:** the value in `parameters.local.json` `workflowNames` for that key is updated to the Azure resource name unconditionally (even if a real value already exists — the exported Azure name is treated as ground truth). Then the `bicep/` folder is scanned for a file that references `workflowNames.<key>` in its content — if found, that file's stem is used as `filename`; otherwise `workflows-{azure-resource-name}` is used. Mapping saved with the resolved filename. File written using that filename.
- **New key entered:** user is prompted to type a camelCase key name. Added to `workflowNames` in `parameters.local.json` as `"newKey": "<azure-resource-name>"`. The `bicep/` folder scan is **not** run (the file does not exist there yet). Filename defaults to `workflows-{azure-resource-name}`. Mapping saved. File written with the default filename.
- **Q to skip:** file is exported with default name, no mapping stored. System will prompt again on next export.

After any mapping interaction, `parameters.local.json` is written back immediately.

---

## Deployment Name Resolution (Pre-flight Check)

Before deploying a Logic App bicep file, the system resolves the expected resource name and checks for naming conflicts. This applies only in **Incremental** deployment mode. If `parameters.local.json` is absent, the pre-flight check is skipped silently.

### Resolution steps

1. Look up the bicep file stem in `.workflow-mappings.json` by matching `mapping.filename` → get `workflowKey` and original Azure name. If no mapping is found for the file, skip the check silently.
2. Resolve the expected deployment name via direct string substitution of parameter values from `parameters.local.json` (read from `data["parameters"][key]["value"]`). Parameter values are substituted verbatim — including any trailing characters (e.g. if `projectSuffix` is `"la-"` the prefix becomes `"la-dev-la-"` with the trailing dash preserved). Full resolved name = `"la-" + environment + "-" + projectSuffix + workflowNames.<workflowKey>` — for example with `environment="dev"`, `projectSuffix="la-"`, `workflowNames.bcDataHandler="11.0-BCData-Handler"` → `"la-dev-la-11.0-BCData-Handler"`. There is no separator between `projectSuffix` and the workflow name value; `projectSuffix` already contains any needed delimiter. The `"la-"` prefix is a hard-coded constant for this tool's Logic App naming convention and is intentional.
3. Check if a resource with that name exists in the target resource group
4. **Name exists in RG** → proceed normally
5. **Name does NOT exist in RG**, but the original Azure name (mapping key) does:
   - Show warning: *"Resource `test-bc` exists but the template will create `la-dev-la-11.0-BCData-Handler` — this creates a new resource rather than updating the existing one."*
   - Options presented to user:
     - **[S] Skip this file** — do not deploy it this run
     - **[U] Use exported name for this deployment** — temporarily override `workflowNames.<key>` to the original Azure name for this deployment only (not saved)
     - **[C] Continue anyway** — proceed and create the new resource name
6. **Complete deployment mode** → skip this check entirely. Azure removes resources not present in the template, so old-named resources are cleaned up naturally.
7. **Fresh RG** (neither name exists) → proceed normally. Resource will be created with the parameters name.

---

## Bicep Header Generation

The static `_KV_HEADER` and `_LA_HEADER_TEMPLATE` constants in `exporter.py` are replaced by a dynamic header generator that reads `parameters.local.json`.

### Reading `parameters.local.json`

Parameters are read from the nested Azure deployment parameters format:

```python
data = json.loads(path.read_text())
params = data["parameters"]  # skip $schema, contentVersion
for key, entry in params.items():
    value = entry["value"]  # the actual parameter value
```

Parameters absent from `parameters.local.json` are simply omitted from the generated header.

### Parameter type inference

The generator reads each parameter from `parameters.local.json` and infers the Bicep type:

| JSON value type | Bicep type |
| --------------- | ---------- |
| `string` | `string` |
| `number` (integer) | `int` |
| `true`/`false` | `bool` |
| `{}` or `{...}` | `object` |
| `[]` or `[...]` | `array` |

### Usage detection

Usage detection runs against the **already-decompiled bicep content** — the resource body text produced by `az bicep decompile` and already present in the file at post-processing time. The header is prepended after this scan; the scan does not look at the header itself.

A parameter is considered **used** if its name appears as a standalone word anywhere in the decompiled resource body (e.g. `logicAppState` appears in `state: logicAppState` after the state-replacement step).

- **Used** → declared normally
- **Not used** → preceded by `#disable-next-line no-unused-params`

### Special cases

- `secretValues` → always decorated with `@secure()` above the declaration
- Object params with `{}` default in `parameters.local.json` → declared with `= {}`
- `workflowNames` → always declared without a default (required param) for Logic Apps
- `logicAppState` → always declared without a default (required param) for Logic Apps

### Logic App var block

After all param declarations, the generator appends:

```bicep
var prefix = 'la-${environment}-${projectSuffix}'
var nameOfLogicApp = '${prefix}-${workflowNames.<workflowKey>}'
```

Where `<workflowKey>` comes from `.workflow-mappings.json` by looking up the Azure resource name. The mapping is always resolved **before** the header is generated — the mapping picklist runs during export, and header generation only runs after a mapping entry exists. If for any reason no mapping is found at header generation time (e.g. the user skipped the picklist), the var line is emitted as `var nameOfLogicApp = '${prefix}-${workflowNames.UNKNOWN}'` as a visible placeholder.

### Key Vault var block

```bicep
// Limitation of Key Vault name to 24 characters
var prefix = 'kv-${environment}'
var nameOfKeyVault = '${prefix}-${uniqueString(resourceGroup().id)}'
```

Key Vault header includes all params from `parameters.local.json` with unused ones suppressed. Key Vault does not use `logicAppState` or `workflowNames` as required params — both get `#disable-next-line no-unused-params`.

### Source of truth

`parameters.local.json` in the current working directory (the project root, e.g. `d:/repos/NewBicep/`) is always used. This file must exist before export can proceed. The deployment pre-flight check also requires `parameters.local.json`; if absent, the check is skipped silently.

---

## WorkflowMappings Module

A new `deployScript/workflow_mappings.py` module encapsulates all mapping logic:

```text
WorkflowMappings
  load() → reads .workflow-mappings.json (returns empty dict if file not found)
  save() → writes .workflow-mappings.json
  find_by_azure_name(azure_name) → Optional[MappingEntry]
  find_by_filename(stem) → Optional[MappingEntry]
  add(azure_name, workflow_key, filename) → MappingEntry
```

`MappingEntry` is a dataclass: `azure_name`, `workflow_key`, `filename`.

The `ResourceExporter` in `exporter.py` takes a `WorkflowMappings` instance. The deployment pre-flight check in `main.py` also uses `WorkflowMappings`.

---

## Out of Scope

- Renaming or reorganising existing entries in `.workflow-mappings.json` via the menu (manual file edit for now)
- Mapping non-Logic-App resources to friendly names
- Syncing changes back from `bicep/` folder renames to `.workflow-mappings.json` automatically (user re-exports or edits mapping manually)
- Supporting multiple parameter files simultaneously (always uses `parameters.local.json`)
