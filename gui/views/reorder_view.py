# gui/views/reorder_view.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout


class ReorderView(QWidget):
    def __init__(self, project_dir, config_manager, bicep_manager, parent=None):
        super().__init__(parent)
        QVBoxLayout(self).addWidget(QLabel("Reorder — coming soon"))
