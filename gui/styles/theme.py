# gui/styles/theme.py

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #181825;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #181825;
    border: none;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 12px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton:disabled { color: #6c7086; background-color: #1e1e2e; }
QPushButton#accent {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#accent:hover { background-color: #b4d0fe; }
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #313244;
}
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QListWidget {
    background-color: #181825;
    border: none;
    outline: none;
}
QListWidget::item:selected { background-color: #313244; }
QScrollBar:vertical {
    background: #1e1e2e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class Color:
    BG = "#181825"
    SURFACE = "#1e1e2e"
    OVERLAY = "#313244"
    BORDER = "#45475a"
    TEXT = "#cdd6f4"
    MUTED = "#6c7086"
    ACCENT = "#89b4fa"
    SUCCESS = "#a6e3a1"
    WARNING = "#f9e2af"
    ERROR = "#f38ba8"
