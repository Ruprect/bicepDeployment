# gui/views/export_view.py
import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt
from deployScript.workflow_mappings import WorkflowMappings
from ..workers.azure_worker import AzureWorker
from ..styles.theme import Color


class ExportView(QWidget):
    def __init__(self, project_dir: Path, config_manager, azure_client, exporter, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.config_manager = config_manager
        self.azure_client = azure_client
        self.exporter = exporter
        self._resources: list = []
        self._workers: list[AzureWorker] = []
        self._output_dir = project_dir / "exported"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        self._fetch_btn = QPushButton("🔄  Fetch Resources")
        self._fetch_btn.clicked.connect(self._fetch_resources)
        toolbar.addWidget(self._fetch_btn)

        self._export_btn = QPushButton("📥  Export Selected")
        self._export_btn.setObjectName("accent")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_selected)
        toolbar.addWidget(self._export_btn)

        toolbar.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {Color.MUTED};")
        toolbar.addWidget(self._count_label)

        layout.addLayout(toolbar)

        # Select All toggle
        select_row = QHBoxLayout()
        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.stateChanged.connect(self._toggle_select_all)
        select_row.addWidget(self._select_all_cb)
        select_row.addStretch()
        layout.addLayout(select_row)

        # Filter bar
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("🔍  Filter resources…")
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        # Resource list
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {Color.SURFACE}; border: 1px solid {Color.OVERLAY};"
            f" border-radius: 6px; }}"
        )
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Output folder row
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder:"))
        self._out_label = QLabel(str(self._output_dir))
        self._out_label.setStyleSheet(f"color: {Color.MUTED};")
        out_row.addWidget(self._out_label)
        out_row.addStretch()
        browse_btn = QPushButton("📁")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        # Status label
        self._status_label = QLabel()
        self._status_label.setStyleSheet(f"color: {Color.MUTED};")
        layout.addWidget(self._status_label)

    def _fetch_resources(self):
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("🔄  Fetching…")
        self._list.clear()
        self._resources.clear()
        rg = self.config_manager.get_resource_group() or ""

        w = AzureWorker(
            callable=self.azure_client.list_resource_group_resources,
            args=(rg,),
        )
        w.result.connect(self._on_resources_loaded)
        w.error.connect(lambda msg: self._status_label.setText(f"Error: {msg}"))
        w.finished.connect(self._on_fetch_done)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_resources_loaded(self, resources):
        self._resources = resources
        # Sort: Logic Apps first, Key Vaults second, rest alphabetically
        def sort_key(r):
            if "Microsoft.Logic/workflows" in r.resource_type:
                return (0, r.name)
            if "Microsoft.KeyVault/vaults" in r.resource_type:
                return (1, r.name)
            return (2, r.name)

        self._resources.sort(key=sort_key)
        self._populate_list(self._resources)

    def _populate_list(self, resources):
        self._list.blockSignals(True)
        self._list.clear()
        for res in resources:
            item = QListWidgetItem(f"{res.name}  —  {res.resource_type}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, res)
            self._list.addItem(item)
        self._list.blockSignals(False)
        self._update_count()

    def _apply_filter(self, text: str):
        text = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            res = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(text not in res.name.lower() and text not in res.resource_type.lower())

    def _toggle_select_all(self, state: int):
        checked = Qt.CheckState.Checked if state == Qt.CheckState.Checked.value else Qt.CheckState.Unchecked
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden():
                item.setCheckState(checked)
        self._list.blockSignals(False)
        self._update_count()

    def _on_item_changed(self, item):
        self._update_count()

    def _update_count(self):
        selected = sum(
            1 for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        )
        self._count_label.setText(f"{selected} selected")
        self._export_btn.setEnabled(selected > 0)

    def _on_fetch_done(self):
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("🔄  Fetch Resources")

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select output folder", str(self._output_dir))
        if path:
            self._output_dir = Path(path)
            self._out_label.setText(str(self._output_dir))

    def _export_selected(self):
        selected = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            return

        self._export_btn.setEnabled(False)
        self._export_btn.setText("📥  Exporting…")

        wm = WorkflowMappings().load()
        params_files = self.config_manager.get_parameter_files()
        params_file = params_files[0] if params_files else None

        output_dir = self._output_dir / datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        def do_export():
            return self.exporter.export_resources(
                selected, output_dir, workflow_mappings=wm, parameters_file=params_file
            )

        w = AzureWorker(callable=do_export, args=())
        w.result.connect(lambda data: self._on_export_done(data, output_dir))
        w.error.connect(lambda msg: self._status_label.setText(f"Export error: {msg}"))
        w.finished.connect(self._on_export_finished)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_export_done(self, result: tuple, output_dir: Path):
        success, total = result
        try:
            rel = output_dir.relative_to(self.project_dir)
        except ValueError:
            rel = output_dir
        self._status_label.setText(
            f"Exported {success}/{total} resources to {rel}"
        )

    def _on_export_finished(self):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("📥  Export Selected")
