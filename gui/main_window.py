# gui/main_window.py
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QStatusBar, QFileDialog
)

from deployScript.config import ConfigManager
from deployScript.bicep_manager import BicepManager
from deployScript.azure_client import AzureClient
from deployScript.exporter import ResourceExporter
from .styles.theme import STYLESHEET
from .widgets.sidebar import SidebarWidget
from .views.deploy_view import DeployView
from .views.config_view import ConfigView
from .views.reorder_view import ReorderView
from .views.export_view import ExportView
from .workers.deploy_worker import DeployWorker


class MainWindow(QMainWindow):
    def __init__(self, project_dir: Path, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self._init_services()
        self._init_ui()
        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("Bicep Deploy")
        self.resize(960, 680)

    def _init_services(self):
        os.chdir(self.project_dir)
        self.config_manager = ConfigManager()
        self.bicep_manager = BicepManager(self.config_manager)
        self.azure_client = AzureClient(self.config_manager)
        self.exporter = ResourceExporter(self.azure_client, self.config_manager)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = SidebarWidget()
        self.sidebar.page_changed.connect(self.switch_to_page)
        self.sidebar.change_folder_requested.connect(self.switch_project)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self._build_views()
        layout.addWidget(self.stack)

        status_bar = QStatusBar()
        status_bar.setStyleSheet("background: #1e1e2e; color: #6c7086; font-size: 10px;")
        self.setStatusBar(status_bar)
        self._update_status_bar()

    def _build_views(self):
        """(Re)create all four views and populate the stack."""
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))

        self.deploy_view = DeployView(self.project_dir, self.config_manager, self.bicep_manager)
        self.deploy_view.deploy_requested.connect(self._start_deploy)
        self.config_view = ConfigView(self.project_dir, self.config_manager, self.azure_client)
        self.reorder_view = ReorderView(self.project_dir, self.config_manager, self.bicep_manager)
        self.export_view = ExportView(self.project_dir, self.config_manager, self.azure_client, self.exporter)

        self.stack.addWidget(self.deploy_view)    # index 0
        self.stack.addWidget(self.config_view)    # index 1
        self.stack.addWidget(self.reorder_view)   # index 2
        self.stack.addWidget(self.export_view)    # index 3

        self._deploy_worker: DeployWorker | None = None

    def _start_deploy(self, templates: list):
        if self._deploy_worker and self._deploy_worker.isRunning():
            return  # already running

        rg = self.config_manager.get_resource_group() or ""
        params = self.config_manager.get_parameter_files()
        params_file = str(params[0].resolve()) if params else ""
        mode = self.config_manager.get_validation_mode() or "Incremental"

        # Map template index back to row index (templates are a subset of all rows)
        all_templates = self.bicep_manager.get_bicep_files()
        template_names = {t.name for t in templates}
        row_indices = [i for i, t in enumerate(all_templates) if t.name in template_names]

        self._deploy_worker = DeployWorker(
            templates=[t.file for t in templates],
            resource_group=rg,
            parameters_file=params_file,
            mode=mode,
        )
        self._deploy_worker.template_started.connect(
            lambda worker_idx: self._on_template_started(row_indices[worker_idx])
        )
        self._deploy_worker.line_output.connect(
            lambda worker_idx, line: self._on_line_output(row_indices[worker_idx], line)
        )
        self._deploy_worker.template_finished.connect(
            lambda worker_idx, success: self._on_template_finished(row_indices[worker_idx], success)
        )
        self._deploy_worker.all_finished.connect(self._on_all_finished)
        self.deploy_view.set_buttons_enabled(False)
        self._deploy_worker.start()

    def _on_template_started(self, row_index: int):
        row = self.deploy_view.get_row_for_index(row_index)
        if row:
            row.set_deploying(True)
        self.statusBar().showMessage(f"⏳ Deploying template {row_index + 1}…")

    def _on_line_output(self, row_index: int, line: str):
        row = self.deploy_view.get_row_for_index(row_index)
        if row:
            row.append_log(line)

    def _on_template_finished(self, row_index: int, success: bool):
        row = self.deploy_view.get_row_for_index(row_index)
        if row:
            row.set_deploying(False)
            if success:
                row.set_succeeded()
            else:
                row.set_failed()

    def _on_all_finished(self):
        self.deploy_view.set_buttons_enabled(True)
        self._update_status_bar()
        self.deploy_view.refresh()

    def switch_to_page(self, index: int):
        self.stack.setCurrentIndex(index)

    def switch_project(self):
        """Open folder picker and reload everything for the new project directory."""
        new_dir = QFileDialog.getExistingDirectory(
            self, "Select project folder", str(self.project_dir)
        )
        if new_dir:
            self.project_dir = Path(new_dir)
            self._init_services()
            self._build_views()
            self._update_status_bar()

    def _update_status_bar(self):
        rg = self.config_manager.get_resource_group() or "no resource group"
        params = self.config_manager.get_parameter_files()
        param_name = params[0].name if params else "no parameter file"
        self.statusBar().showMessage(
            f"📁 {self.project_dir}   ·   🗂 {rg}   ·   📄 {param_name}"
        )
