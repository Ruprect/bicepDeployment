# gui/views/reorder_view.py
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..styles.theme import Color


class _RowItemWidget(QWidget):
    enabled_changed = pyqtSignal(str, bool)

    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)

        drag_label = QLabel("⠿")
        drag_label.setStyleSheet(f"color: {Color.MUTED};")
        row.addWidget(drag_label)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(template.enabled)
        row.addWidget(self._checkbox)

        self._name_label = QLabel(template.file.name)
        self._name_label.setStyleSheet(
            f"color: {Color.TEXT};" if template.enabled else
            f"color: {Color.MUTED}; text-decoration: line-through;"
        )
        row.addWidget(self._name_label)
        row.addStretch()

        # Wire after both widgets exist so _update_label_style can reference _name_label
        self._checkbox.stateChanged.connect(self._on_state_changed)

    def _on_state_changed(self, state: int):
        enabled = state == Qt.CheckState.Checked.value
        self._name_label.setStyleSheet(
            f"color: {Color.TEXT};" if enabled else
            f"color: {Color.MUTED}; text-decoration: line-through;"
        )
        self.enabled_changed.emit(self.template.name, enabled)


class ReorderView(QWidget):
    order_saved = pyqtSignal()   # emitted when Save Order is clicked

    def __init__(self, project_dir: Path, config_manager, bicep_manager, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.config_manager = config_manager
        self.bicep_manager = bicep_manager
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel("Drag rows to reorder  ·  checkbox to enable/disable")
        hint.setStyleSheet(f"color: {Color.MUTED}; font-size: 10px;")
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setStyleSheet(
            f"QListWidget {{ background: {Color.SURFACE}; border: 1px solid {Color.OVERLAY};"
            f" border-radius: 6px; }}"
            f"QListWidget::item {{ border-bottom: 1px solid {Color.OVERLAY}; padding: 2px; }}"
        )
        layout.addWidget(self._list)

        self._save_btn = QPushButton("💾  Save Order")
        self._save_btn.setObjectName("accent")
        self._save_btn.clicked.connect(self._save_order)
        layout.addWidget(self._save_btn)

    def refresh(self):
        self._list.clear()
        for tpl in self.bicep_manager.get_bicep_files():
            item = QListWidgetItem(self._list)
            widget = _RowItemWidget(tpl)
            widget.enabled_changed.connect(
                lambda name, enabled: self.bicep_manager.set_template_enabled(name, enabled)
            )
            item.setSizeHint(widget.sizeHint())
            self._list.setItemWidget(item, widget)

    def _save_order(self):
        new_order = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            widget = self._list.itemWidget(item)
            if widget:
                new_order.append(widget.template.name)
        self.bicep_manager.reorder_templates(new_order)
        self.order_saved.emit()
