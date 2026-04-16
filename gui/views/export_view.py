# gui/views/export_view.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout


class ExportView(QWidget):
    def __init__(self, project_dir, config_manager, azure_client, exporter, parent=None):
        super().__init__(parent)
        QVBoxLayout(self).addWidget(QLabel("Export — coming soon"))
