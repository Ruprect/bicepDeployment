# gui/views/config_view.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout


class ConfigView(QWidget):
    def __init__(self, project_dir, config_manager, azure_client, parent=None):
        super().__init__(parent)
        QVBoxLayout(self).addWidget(QLabel("Config — coming soon"))
