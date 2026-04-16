# tests/gui/test_app.py
from pathlib import Path


def test_main_window_instantiates(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    assert window.windowTitle() == "Bicep Deploy"


def test_main_window_has_four_pages(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    assert window.stack.count() == 4
