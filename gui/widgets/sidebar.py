# gui/widgets/sidebar.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from ..styles.theme import Color

_NAV_ITEMS = [
    (0, "🚀", "Deploy"),
    (1, "⚙️", "Config"),
    (2, "↕️", "Reorder"),
    (3, "📤", "Export"),
]


class SidebarWidget(QWidget):
    page_changed = pyqtSignal(int)
    change_folder_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(130)
        self.setStyleSheet(f"background-color: {Color.SURFACE}; border-right: 1px solid {Color.OVERLAY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("BICEP DEPLOY")
        header.setStyleSheet(
            f"color: {Color.TEXT}; font-weight: bold; font-size: 11px;"
            f" letter-spacing: 1px; padding: 14px 12px 10px;"
            f" border-bottom: 1px solid {Color.OVERLAY};"
        )
        layout.addWidget(header)

        # Nav buttons
        self._nav_buttons: dict[int, QPushButton] = {}
        for index, icon, label in _NAV_ITEMS:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setFlat(True)
            btn.setStyleSheet(self._nav_style(active=False))
            btn.clicked.connect(lambda checked, i=index: self._select(i))
            layout.addWidget(btn)
            self._nav_buttons[index] = btn

        layout.addStretch()

        # Change folder button
        folder_btn = QPushButton("📁  Change folder")
        folder_btn.setStyleSheet(
            f"color: {Color.ACCENT}; background: {Color.OVERLAY}; border: none;"
            f" border-radius: 4px; padding: 6px; margin: 8px;"
        )
        folder_btn.clicked.connect(self.change_folder_requested)
        layout.addWidget(folder_btn)

        self._select(0)  # start on Deploy

    def _select(self, index: int):
        for i, btn in self._nav_buttons.items():
            btn.setStyleSheet(self._nav_style(active=(i == index)))
        self.page_changed.emit(index)

    @staticmethod
    def _nav_style(active: bool) -> str:
        if active:
            return (
                f"text-align: left; color: {Color.TEXT}; background: {Color.OVERLAY};"
                f" border-left: 2px solid {Color.ACCENT}; border-radius: 0; padding: 7px 12px;"
            )
        return (
            f"text-align: left; color: {Color.MUTED}; background: transparent;"
            f" border: none; border-radius: 0; padding: 7px 12px;"
        )
