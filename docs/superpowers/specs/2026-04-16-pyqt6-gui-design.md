# PyQt6 GUI Design Spec

**Date:** 2026-04-16  
**Project:** bicepDeployment  
**Goal:** Add a PyQt6 desktop GUI as an alternative frontend to the existing text-based CLI. Both modes share the same Python service layer (`deployScript/`). The CLI is not modified.

---

## 1. Architecture

### Principle
Two independent frontends, one shared service layer.

- `deployScript/` — unchanged. Contains all business logic: `AzureClient`, `BicepManager`, `DeploymentManager`, `ResourceExporter`, `ConfigManager`, `WorkflowMappings`.
- `gui/` — new folder. All PyQt6 code lives here. Imports from `deployScript/` for data and state.
- `deploy.py` — existing CLI entry point, untouched.
- `python -m gui` — new GUI entry point, launched from the project directory.

### Working Directory
The GUI is launched from the project directory (same as the CLI). On startup it reads `bicep/`, `parameters.local.json`, and `.deployment-settings.json` from `Path.cwd()`. A **"Change folder"** button in the sidebar opens a `QFileDialog` to switch project directories without restarting the app.

### Service Classes Used by the GUI

| GUI need | Service class |
|----------|--------------|
| List templates, read order/hash/status | `BicepManager` |
| Read/write config (RG, params, subscription) | `ConfigManager` |
| List Azure subscriptions, RGs, resources | `AzureClient` |
| Export resources to Bicep | `ResourceExporter` |
| Workflow key/filename mappings | `WorkflowMappings` |

### Deployment Subprocess
`deployment_manager.DeploymentManager.deploy_bicep_template` uses `print`/`input` and cannot be used from a GUI thread. Instead, `DeployWorker` (a `QThread`) constructs and runs `az deployment group create` via `subprocess.Popen` with `stdout=PIPE, stderr=PIPE`, streaming each output line as a Qt signal.

`DeployWorker.__init__` accepts the following constructor arguments, read from `ConfigManager` at the point the user clicks Deploy:

- `templates: list[Path]` — ordered list of `.bicep` files to deploy
- `resource_group: str` — from `ConfigManager`
- `parameters_file: str` — absolute path, from `ConfigManager`
- `mode: str` — `"Incremental"` or `"Complete"`, from `ConfigManager`

The worker builds: `az deployment group create --resource-group <rg> --mode <mode> --template-file <file> --parameters @<params_file>`

---

## 2. Folder Structure

```
d:/repos/bicepDeployment/
  deployScript/          ← unchanged
  gui/
    __init__.py          ← exposes main() entry point
    app.py               ← QApplication init, MainWindow creation
    main_window.py       ← MainWindow: sidebar + QStackedWidget
    views/
      __init__.py
      deploy_view.py     ← template list with inline status rows
      config_view.py     ← settings form (RG, params, subscription, etc.)
      reorder_view.py    ← drag-and-drop template order + enable/disable
      export_view.py     ← resource picker + export trigger
    widgets/
      __init__.py
      template_row.py    ← collapsible row: status indicator + log panel
      sidebar.py         ← navigation sidebar with icons + folder button
    workers/
      __init__.py
      deploy_worker.py   ← QThread: streams az subprocess output
      azure_worker.py    ← QThread: fetches Azure resources/RGs/subscriptions
    styles/
      theme.py           ← QSS dark stylesheet + Color constants
```

---

## 3. Main Window

**Layout:** Fixed sidebar (130 px) on the left + `QStackedWidget` for the main content area.

**Sidebar nav items:**
1. 🚀 Deploy
2. ⚙️ Config
3. ↕️ Reorder
4. 📤 Export

**Bottom of sidebar:** "📁 Change folder" button — opens `QFileDialog.getExistingDirectory`, reinitialises `BicepManager` and `ConfigManager` with the new path, refreshes all views.

**Status bar** (bottom of main content): shows current project path · resource group · parameter file · live deploy progress when active.

---

## 4. Deploy View

**Toolbar:** `▶ Deploy All` · `▶ Deploy Selected` · `🔄 Refresh` · Validation mode pill (cycles All → Changed → Skip on click).

**Template list:** A scrollable `QScrollArea` containing one `TemplateRow` widget per Bicep file.

### TemplateRow widget

Each row has two states:

**Collapsed:**
```
[✓] 01  workflows-bc.bicep              ✅ Up to date    ▼
```

**Expanded (click ▼ to toggle):**
```
[✓] 02  keyvault.bicep    [████████░░] ⏳ 42s           ▲
─────────────────────────────────────────────────────────
[10:42:01] Starting deployment: keyvault.bicep
[10:42:02] az deployment group create --resource-group rg-dev-accepttest
[10:42:10] ⏳ Waiting for Azure response…
```

**Auto-expand on failure** — when `DeployWorker` emits `template_finished(index, success=False)`, the row's log panel opens automatically and the row border turns red.

**Status icons:**
| State | Display |
|-------|---------|
| Up to date | `✅ Up to date` (green) |
| Changed | `🟡 Changed` (amber) |
| Deploying | progress bar + elapsed seconds (blue) |
| Failed | `❌ Failed` (red, auto-expanded) |
| Never deployed | `⚪ Never deployed` (grey) |
| Disabled | strikethrough text, faded (checkbox unchecked) |

**Checkbox** on each row: enables/disables the template (persisted via `BicepManager`). Disabled rows are visually faded.

**Deploy All** — runs all enabled templates in sequence, one `DeployWorker` at a time.  
**Deploy Selected** — deploys only rows whose checkboxes are checked.

---

## 5. Config View

Form with dropdowns and file pickers, changes applied on widget change (no separate Save button):

| Field | Widget | Source |
|-------|--------|--------|
| Azure login status | read-only banner (green/red) | `AzureClient.check_login()` |
| Subscription | `QComboBox` + 🔄 refresh | `AzureClient.list_subscriptions()` via `AzureWorker` |
| Resource Group | `QComboBox` + 🔄 refresh | `AzureClient.list_resource_groups()` via `AzureWorker` |
| Parameter File | `QComboBox` + 📁 browse | scans `cwd()` for `parameters*.json` |
| Deployment Mode | `QComboBox` (Incremental / Complete) | `ConfigManager` |
| Validation | `QComboBox` (All / Changed / Skip) | `ConfigManager` |
| Re-login | button | runs `az login` in `AzureWorker` via `subprocess.Popen` with no stdout/stderr capture, so the OS handles browser redirection. The button is disabled while the subprocess is running. |

Changes are written to `ConfigManager` immediately on widget change and persisted to `.deployment-settings.json`.

---

## 6. Reorder View

A `QListWidget` in drag-and-drop mode (`InternalMove`). Each item shows:
```
⠿  [✓]  01  workflows-bc.bicep
```

- **Drag handle** (⠿) — drag rows up/down to reorder. No ▲▼ buttons.
- **Checkbox** — enable/disable the template. Writes to the same `BicepManager` enabled-state field used by the Deploy view. The Deploy view refreshes automatically when the user navigates back to it.
- **Save Order** button at the bottom — writes the reordered sequence to `BicepManager` and refreshes the Deploy view.

---

## 7. Export View

**Toolbar:** `🔄 Fetch Resources` (loads from Azure via `AzureWorker`) · `📥 Export Selected`.

**Select All toggle:** A "☐ Select All / ☑ Deselect All" checkbox above the list — toggles all items.

**Resource list:** Scrollable `QListWidget` with checkboxes. Each item shows resource name, type icon, and resource type. Resources grouped by type (Logic Apps first, then Key Vaults, then others).

**Filter bar:** `QLineEdit` for instant text filtering of the resource list.

**Output folder:** Read-only text field showing `exported/` relative path + 📁 browse button to change it.

**Export flow:** clicking `Export Selected` launches `ResourceExporter.export_resources()` in an `AzureWorker` thread. A progress indicator replaces the toolbar during export. On completion, `AzureWorker` emits `result(data)` where `data` is a `tuple[int, int]` of `(success_count, total_count)` — the export view uses this to display `Exported N/M resources to exported/YYYY-MM-DD_HHMMSS/`.

---

## 8. Threading Model

All `az` subprocess calls and file I/O that may block run in `QThread` workers. Workers communicate with the UI exclusively via Qt signals.

### DeployWorker
```
Signals:
  line_output(template_index: int, line: str)
  template_started(template_index: int)
  template_finished(template_index: int, success: bool)
  all_finished()
```
Runs templates sequentially. Streams `stdout`/`stderr` line-by-line via `readline()`.

### AzureWorker
```
Signals:
  result(data: object)
  error(message: str)
  finished()
```
Generic worker: accepts a callable + args, runs it in background, emits result or error.

---

## 9. Entry Point & Launch

```python
# gui/__init__.py
from .app import main
```

```python
# gui/app.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from .main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow(project_dir=Path.cwd())
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```

**Launch command** (from project directory):
```bash
python -m gui
```

**Dependency:** `pip install PyQt6` (added to `requirements.txt`).

---

## 10. Styling

A single QSS dark stylesheet in `gui/styles/theme.py` provides the Catppuccin-inspired dark palette used in the mockups:

| Role | Colour |
|------|--------|
| Background | `#181825` |
| Surface | `#1e1e2e` |
| Overlay | `#313244` |
| Text | `#cdd6f4` |
| Muted text | `#6c7086` |
| Accent (blue) | `#89b4fa` |
| Success (green) | `#a6e3a1` |
| Warning (amber) | `#f9e2af` |
| Error (red) | `#f38ba8` |

---

## 11. Out of Scope

- The text CLI (`deploy.py`, `deployScript/menu.py`, `deployScript/main.py`) is not modified.
- No Chrome profile setting in the GUI (terminal-specific).
- No console width setting in the GUI (not applicable).
- No packaging/installer (run as a Python script).
- No unit tests for GUI widgets in this phase (service layer is already tested).
