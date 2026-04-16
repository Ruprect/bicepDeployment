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


if __name__ == "__main__":
    main()
