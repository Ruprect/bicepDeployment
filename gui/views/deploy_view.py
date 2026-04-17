# gui/views/deploy_view.py
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QLabel, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from ..widgets.template_row import TemplateRowWidget
from ..styles.theme import Color

_VALIDATION_MODES = ["All", "Changed", "Skip"]


class DeployView(QWidget):
    deploy_requested = pyqtSignal(list)   # list of BicepTemplate to deploy

    def __init__(self, project_dir: Path, config_manager, bicep_manager, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.config_manager = config_manager
        self.bicep_manager = bicep_manager
        self._rows: list[TemplateRowWidget] = []
        self._validation_idx = 0
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: {Color.SURFACE}; border-bottom: 1px solid {Color.OVERLAY};")
        tb_row = QHBoxLayout(toolbar)
        tb_row.setContentsMargins(12, 8, 12, 8)

        self._btn_all = QPushButton("▶  Deploy All")
        self._btn_all.setObjectName("accent")
        self._btn_all.clicked.connect(self._deploy_all)
        tb_row.addWidget(self._btn_all)

        self._btn_selected = QPushButton("▶  Deploy Selected")
        self._btn_selected.clicked.connect(self._deploy_selected)
        tb_row.addWidget(self._btn_selected)

        self._btn_refresh = QPushButton("🔄  Refresh")
        self._btn_refresh.clicked.connect(self.refresh)
        tb_row.addWidget(self._btn_refresh)

        tb_row.addStretch()

        self._validation_pill = QPushButton()
        self._validation_pill.setStyleSheet(
            f"background: {Color.OVERLAY}; color: {Color.TEXT}; border-radius: 10px; padding: 2px 10px;"
        )
        self._validation_pill.clicked.connect(self._cycle_validation)
        tb_row.addWidget(self._validation_pill)
        self._update_validation_pill()

        layout.addWidget(toolbar)

        # Scrollable template list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self):
        """Reload templates from BicepManager and rebuild the row list."""
        # Remove existing rows (keep the trailing stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        templates = self.bicep_manager.get_bicep_files()
        for tpl in templates:
            row = TemplateRowWidget(tpl)
            row.enabled_changed.connect(
                lambda name, enabled: self.bicep_manager.set_template_enabled(name, enabled)
            )
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

    def _deploy_all(self):
        templates = [r.template for r in self._rows if r.template.enabled]
        if templates:
            self.deploy_requested.emit(templates)

    def _deploy_selected(self):
        templates = [r.template for r in self._rows if r._checkbox.isChecked()]
        if templates:
            self.deploy_requested.emit(templates)

    def _cycle_validation(self):
        self._validation_idx = (self._validation_idx + 1) % len(_VALIDATION_MODES)
        mode = _VALIDATION_MODES[self._validation_idx]
        self.config_manager.set_validation_mode(mode)
        self._update_validation_pill()

    def _update_validation_pill(self):
        modes = self.config_manager.get_validation_mode() or "Changed"
        self._validation_pill.setText(f"Validation: {modes}")

    def get_row_for_index(self, index: int) -> TemplateRowWidget | None:
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def set_buttons_enabled(self, enabled: bool):
        self._btn_all.setEnabled(enabled)
        self._btn_selected.setEnabled(enabled)
