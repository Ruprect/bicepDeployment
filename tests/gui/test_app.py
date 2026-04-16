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


def test_sidebar_switches_page(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    window.show()

    # Click Config (index 1)
    window.sidebar._select(1)
    assert window.stack.currentIndex() == 1

    # Click Deploy (index 0)
    window.sidebar._select(0)
    assert window.stack.currentIndex() == 0
